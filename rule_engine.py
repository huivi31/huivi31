# -*- coding: utf-8 -*-
"""
独立规则引擎 - 多层审核流水线
从 CentralInspectorAgent 中解耦出来的纯规则引擎

5层检测链：
  Layer 1: 关键词精确匹配（含去空格/符号）
  Layer 2: 拼音还原匹配（谐音检测）+ 优化语义分析
  Layer 3: 正则模式匹配（风险句式）
  Layer 4: 用户自定义变体词库
  Layer 5: LLM 语义兜底（可选）

v2.2 - Layer 2 集成优化语义分析模块
"""

import re
import time
import json

try:
    from pypinyin import lazy_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

# v2.2: 优化的语义分析模块
try:
    from semantic_analyzer import SEMANTIC_ANALYZER
    HAS_SEMANTIC_ANALYZER = True
except ImportError:
    SEMANTIC_ANALYZER = None
    HAS_SEMANTIC_ANALYZER = False


class AuditResult:
    """审核结果"""
    def __init__(self):
        self.detected = False
        self.hit_layer = ""          # keyword / pinyin / regex / variant / semantic
        self.hit_layer_num = 0       # 1-5
        self.hit_rules = []
        self.hit_keywords = []
        self.detection_reason = ""
        self.confidence = 0.0
        self.processing_time = 0.0
    
    def to_dict(self):
        return {
            "detected": self.detected,
            "hit_layer": self.hit_layer,
            "hit_layer_num": self.hit_layer_num,
            "hit_rules": self.hit_rules,
            "hit_keywords": self.hit_keywords,
            "detection_reason": self.detection_reason,
            "confidence": self.confidence,
            "processing_time": self.processing_time,
        }
    
    def block(self, layer: str, layer_num: int, reason: str, confidence: float,
              keywords: list = None, rules: list = None):
        """标记为拦截"""
        self.detected = True
        self.hit_layer = layer
        self.hit_layer_num = layer_num
        self.detection_reason = reason
        self.confidence = confidence
        if keywords:
            self.hit_keywords = keywords
        if rules:
            self.hit_rules = rules
        return self


class RuleEngine:
    """
    独立多层审核引擎
    
    不依赖 LLM 做主要判定（LLM 仅作为可选兜底层）
    每层返回 hit_layer 信息，告诉攻击 Agent 是被哪层拦截的
    """
    
    # 内置敏感词库（基础词 → 常见变体列表）
    BUILTIN_SENSITIVE_WORDS = {
        "习近平": ["xjp", "XJP", "习大大", "习主席", "刑平", "维尼", "🐻", 
                  "小熊维尼", "噗噗熊", "包子", "庆丰", "梁家河", "翠",
                  "平子", "瓶子", "刁大大", "xi jin ping", "winnie"],
        "共产党": ["gcd", "GCD", "土共", "中共", "tg", "TG", "CCP", "ccp",
                  "躬惨裆", "赵家人"],
        "六四": ["64", "8964", "八九六四", "五月三十五", "5月35日", "天安门事件",
                "坦克人", "liu si", "May35", "tiananmen"],
        "政府": ["zf", "ZF", "正负", "zhengfu", "govt"],
        "毛泽东": ["腊肉", "教员", "太祖", "mzd", "MZD"],
        "文革": ["文化大革命", "十年浩劫", "文化大割命"],
        "法轮功": ["flg", "FLG", "轮子", "大法"],
        "台独": ["湾湾", "台巴子", "呆湾"],
        "新疆": ["集中营", "再教育营", "棉花事件"],
        "香港": ["反送中", "光复香港", "揽炒"],
    }
    
    # 风险句式正则
    RISK_PATTERNS = [
        r"打倒.{0,4}(政府|政权|体制|制度)",
        r"推翻.{0,4}(政府|政权|体制|制度)",
        r"颠覆.{0,4}(政权|国家)",
        r"(独裁|专制).{0,4}(政府|政权|体制|国家)",
        r"(暴政|暴君|独裁者)",
        r"(民主|自由).{0,2}(万岁|必胜)",
        r"共匪|赤匪",
        r"亡国|灭党",
        r"(武装|暴力).{0,4}(起义|革命|反抗)",
        r"寻衅滋事",
        r"(被|遭).{0,2}(失踪|喝茶|约谈|带走)",
        r"铁拳.{0,4}(砸|落|来)",
    ]
    
    def __init__(self):
        # 用户设置的规则
        self.rules = []
        self.rule_keywords = {}  # rule_id -> [keywords]
        
        # 用户自定义变体词库（通过投喂学习）
        self.custom_variants = {}  # base_word -> [variants]
        
        # LLM 客户端（可选）
        self.llm_client = None
        self.llm_provider = ""
        self.llm_model = ""
        
        # 统计
        self.stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_layer": {"keyword": 0, "pinyin": 0, "regex": 0, "variant": 0, "semantic": 0},
            "by_keyword": {},
            "by_technique": {},
        }
    
    def set_rules(self, rules: list):
        """设置审核规则"""
        self.rules = rules
        self.rule_keywords = {}
        for rule in rules:
            rule_id = rule.get("id", "")
            keywords = rule.get("keywords", [])
            self.rule_keywords[rule_id] = keywords
    
    def set_llm(self, client, provider: str, model: str):
        """设置可选的 LLM 兜底"""
        self.llm_client = client
        self.llm_provider = provider
        self.llm_model = model
    
    def add_custom_variants(self, base_word: str, variants: list):
        """添加自定义变体词"""
        if base_word not in self.custom_variants:
            self.custom_variants[base_word] = []
        for v in variants:
            if v and v not in self.custom_variants[base_word]:
                self.custom_variants[base_word].append(v)
    
    def inspect(self, content: str, technique_used: str = "") -> AuditResult:
        """
        主审核入口 - 5层流水线
        
        Returns:
            AuditResult with hit_layer indicating which layer caught it
        """
        self.stats["total_checked"] += 1
        result = AuditResult()
        
        if not content or not content.strip():
            return result
        
        start_time = time.time()
        content_lower = content.lower()
        # 去除空格、标点、特殊符号后的版本
        content_clean = re.sub(r'[\s\.\,\;\:\!\?\·\|\-\_\/\\。，；：！？、\u200b\u200c\u200d\ufeff]', '', content)
        content_clean_lower = content_clean.lower()
        
        # ========== Layer 1: 关键词精确匹配 ==========
        result = self._layer1_keyword(content, content_lower, content_clean, content_clean_lower, result)
        if result.detected:
            result.processing_time = round(time.time() - start_time, 3)
            self._update_stats(result, technique_used)
            return result
        
        # ========== Layer 2: 拼音还原匹配 ==========
        result = self._layer2_pinyin(content, content_clean, result)
        if result.detected:
            result.processing_time = round(time.time() - start_time, 3)
            self._update_stats(result, technique_used)
            return result
        
        # ========== Layer 3: 正则模式匹配 ==========
        result = self._layer3_regex(content, content_clean, result)
        if result.detected:
            result.processing_time = round(time.time() - start_time, 3)
            self._update_stats(result, technique_used)
            return result
        
        # ========== Layer 4: 自定义变体词库 ==========
        result = self._layer4_custom_variants(content, content_lower, content_clean_lower, result)
        if result.detected:
            result.processing_time = round(time.time() - start_time, 3)
            self._update_stats(result, technique_used)
            return result
        
        # ========== Layer 5: LLM 语义兜底 ==========
        result = self._layer5_semantic(content, result)
        result.processing_time = round(time.time() - start_time, 3)
        self._update_stats(result, technique_used)
        return result
    
    def _layer1_keyword(self, content, content_lower, content_clean, content_clean_lower, result):
        """Layer 1: 关键词精确匹配"""
        
        # 1a: 用户规则关键词
        for rule in self.rules:
            keywords = rule.get("keywords", [])
            for kw in keywords:
                if not kw or len(kw) < 2:
                    continue
                if kw in content or kw.lower() in content_lower or kw in content_clean:
                    result.block(
                        layer="keyword", layer_num=1,
                        reason=f"关键词匹配: {kw}",
                        confidence=1.0,
                        keywords=[kw], rules=[rule["id"]]
                    )
                    return result
        
        # 1b: 内置敏感词库
        for base_word, variants in self.BUILTIN_SENSITIVE_WORDS.items():
            if base_word in content_clean:
                result.block(
                    layer="keyword", layer_num=1,
                    reason=f"敏感词: {base_word}",
                    confidence=0.95,
                    keywords=[base_word]
                )
                return result
            for variant in variants:
                if variant.lower() in content_clean_lower or variant in content:
                    result.block(
                        layer="keyword", layer_num=1,
                        reason=f"敏感词变体: {variant} (原词:{base_word})",
                        confidence=0.9,
                        keywords=[f"{base_word}→{variant}"]
                    )
                    return result
        
        return result
    
    def _layer2_pinyin(self, content, content_clean, result):
        """
        Layer 2: 拼音还原 + 语义分析 (v2.2优化)
        
        先做拼音检测,如果通过再进行语义分析
        """
        # 2a: 拼音还原检测
        if HAS_PYPINYIN:
            try:
                # 将内容转为拼音
                content_pinyin = ''.join(lazy_pinyin(content_clean))
                
                # 将所有敏感词也转为拼音，对比
                all_sensitive = list(self.BUILTIN_SENSITIVE_WORDS.keys())
                for rule in self.rules:
                    for kw in rule.get("keywords", []):
                        if kw and len(kw) >= 2:
                            all_sensitive.append(kw)
                
                for word in all_sensitive:
                    word_pinyin = ''.join(lazy_pinyin(word))
                    if len(word_pinyin) >= 4 and word_pinyin in content_pinyin:
                        # 确认不是 Layer 1 已经抓过的（原文直接匹配）
                        if word not in content_clean:
                            result.block(
                                layer="pinyin", layer_num=2,
                                reason=f"拼音还原命中: 内容拼音含'{word_pinyin}' (原词:{word})",
                                confidence=0.85,
                                keywords=[f"拼音:{word}"]
                            )
                            return result
            except Exception:
                pass
        
        # 2b: 语义分析 (v2.2新增)
        if HAS_SEMANTIC_ANALYZER:
            try:
                semantic_result = SEMANTIC_ANALYZER.analyze(content, self.rules)
                if semantic_result.get("is_sensitive") and semantic_result.get("confidence", 0) >= 0.5:
                    # 提取匹配的模式名称
                    patterns = semantic_result.get("matched_patterns", [])
                    pattern_names = [p.get("name", "未知") for p in patterns[:3]]
                    
                    result.block(
                        layer="semantic", layer_num=2,
                        reason=f"语义分析命中: {semantic_result.get('details', '可疑内容')}",
                        confidence=semantic_result.get("confidence", 0.5),
                        keywords=pattern_names if pattern_names else ["语义模式"]
                    )
                    return result
            except Exception:
                pass
        
        return result
    
    def _layer3_regex(self, content, content_clean, result):
        """Layer 3: 正则模式匹配"""
        for pattern in self.RISK_PATTERNS:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    result.block(
                        layer="regex", layer_num=3,
                        reason=f"风险句式: {pattern}",
                        confidence=0.8,
                        keywords=[pattern]
                    )
                    return result
                if re.search(pattern, content_clean, re.IGNORECASE):
                    result.block(
                        layer="regex", layer_num=3,
                        reason=f"风险句式(清洗后): {pattern}",
                        confidence=0.75,
                        keywords=[pattern]
                    )
                    return result
            except re.error:
                continue
        
        return result
    
    def _layer4_custom_variants(self, content, content_lower, content_clean_lower, result):
        """Layer 4: 用户自定义变体词库（通过投喂学习的）"""
        for base_word, variants in self.custom_variants.items():
            for variant in variants:
                if variant.lower() in content_lower or variant.lower() in content_clean_lower:
                    result.block(
                        layer="variant", layer_num=4,
                        reason=f"自定义变体: {variant} (原词:{base_word})",
                        confidence=0.85,
                        keywords=[f"自定义:{base_word}→{variant}"]
                    )
                    return result
        
        return result
    
    def _layer5_semantic(self, content, result):
        """Layer 5: LLM 语义兜底（可选）"""
        if not self.llm_client or not self.rules:
            return result
        
        rules_desc = "\n".join([f"- {r.get('text', '')}" for r in self.rules])
        prompt = f"""你是严格的内容审核员。请判断以下内容是否违反审核规则，包括隐晦、暗示、影射的表达。

审核规则：
{rules_desc}

待审内容：
{content}

请判断：
1. 是否违规（即使是隐晦/暗示也算违规）
2. 违规原因（如果违规）
3. 置信度（0-1）

注意：使用谐音、拼音缩写、空格分隔、emoji替代等手法绕过审核的内容都算违规。
用JSON格式输出：{{"violated": true/false, "reason": "...", "confidence": 0.X}}
只输出JSON。"""
        
        try:
            llm_response = self._call_llm(prompt)
            if llm_response:
                if llm_response.startswith("```"):
                    llm_response = llm_response.split("```")[1]
                    if llm_response.startswith("json"):
                        llm_response = llm_response[4:]
                analysis = json.loads(llm_response.strip())
                if analysis.get("violated"):
                    result.block(
                        layer="semantic", layer_num=5,
                        reason=f"语义检测: {analysis.get('reason', '')}",
                        confidence=analysis.get("confidence", 0.7),
                    )
        except Exception:
            pass
        
        return result
    
    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """调用 LLM"""
        if not self.llm_client:
            return ""
        try:
            if self.llm_provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=300
                )
                return response.choices[0].message.content.strip()
            elif self.llm_provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": 300}
                )
                return response.text.strip()
        except Exception:
            return ""
        return ""
    
    def _update_stats(self, result: AuditResult, technique_used: str):
        """更新统计"""
        if result.detected:
            self.stats["total_detected"] += 1
            if result.hit_layer:
                self.stats["by_layer"][result.hit_layer] = \
                    self.stats["by_layer"].get(result.hit_layer, 0) + 1
            if technique_used:
                self.stats["by_technique"][technique_used] = \
                    self.stats["by_technique"].get(technique_used, 0) + 1
            for kw in result.hit_keywords:
                self.stats["by_keyword"][kw] = self.stats["by_keyword"].get(kw, 0) + 1
        else:
            self.stats["total_bypassed"] += 1
    
    def get_stats(self) -> dict:
        """获取统计"""
        stats = dict(self.stats)
        total = stats["total_checked"]
        if total > 0:
            stats["detection_rate"] = round(stats["total_detected"] / total * 100, 1)
            stats["bypass_rate"] = round(stats["total_bypassed"] / total * 100, 1)
        else:
            stats["detection_rate"] = 0
            stats["bypass_rate"] = 0
        return stats
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_layer": {"keyword": 0, "pinyin": 0, "regex": 0, "variant": 0, "semantic": 0},
            "by_keyword": {},
            "by_technique": {},
        }
    
    def get_layer_description(self, layer_num: int) -> str:
        """获取层级描述，用于反馈给攻击Agent"""
        descriptions = {
            1: "关键词/敏感词精确匹配（含去空格后匹配）",
            2: "拼音还原检测（谐音→原词）",
            3: "风险句式正则匹配",
            4: "自定义变体词库匹配",
            5: "LLM语义深度分析",
        }
        return descriptions.get(layer_num, "未知层")


# 全局规则引擎实例
RULE_ENGINE = RuleEngine()
