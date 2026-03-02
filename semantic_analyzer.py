# -*- coding: utf-8 -*-
"""
语义分析模块 (L2层优化)
v2.2.0 - 使用规则引擎+模式匹配,减少LLM依赖
"""

import re
from typing import Dict, List, Tuple, Optional


class SemanticAnalyzer:
    """优化的语义分析器"""
    
    def __init__(self):
        # 敏感模式库
        self.sensitive_patterns = self._build_patterns()
        
        # 上下文伪装检测
        self.context_keywords = {
            "政治": ["政策", "政府", "领导", "官员", "政治", "体制", "制度"],
            "经济": ["经济", "金融", "货币", "投资", "股市", "房价"],
            "社会": ["社会", "民生", "就业", "教育", "医疗", "养老"],
        }
        
        # 情感极性词
        self.negative_words = {
            "质疑", "批判", "反对", "抗议", "不满", "愤怒", 
            "腐败", "黑暗", "压迫", "剥削", "独裁", "专制"
        }
        
        self.positive_words = {
            "支持", "赞同", "拥护", "认可", "满意", "欢迎"
        }
    
    def _build_patterns(self) -> List[Dict]:
        """构建敏感模式库"""
        return [
            # 谐音变体
            {
                "name": "谐音政治",
                "pattern": r"(正负|政腐|政付|正付|政富|政服)",
                "score": 0.8,
                "category": "politics"
            },
            {
                "name": "谐音领导",
                "pattern": r"(领倒|领导|岭导|另导|令导)",
                "score": 0.7,
                "category": "politics"
            },
            {
                "name": "谐音专家",
                "pattern": r"(砖家|专家|砖+家)",
                "score": 0.6,
                "category": "sarcasm"
            },
            
            # 拼音缩写
            {
                "name": "拼音ZF",
                "pattern": r"\b(zf|ZF|z\.?f\.?|Zf)\b",
                "score": 0.8,
                "category": "politics"
            },
            {
                "name": "拼音GCD",
                "pattern": r"\b(gcd|GCD|g\.?c\.?d\.?)\b",
                "score": 0.9,
                "category": "politics"
            },
            {
                "name": "拼音TG",
                "pattern": r"\b(tg|TG|t\.?g\.?)\b",
                "score": 0.85,
                "category": "politics"
            },
            
            # 符号替代
            {
                "name": "符号混淆",
                "pattern": r"(政[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]府|领[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]导)",
                "score": 0.75,
                "category": "evasion"
            },
            
            # emoji混淆
            {
                "name": "emoji政治",
                "pattern": r"(🐻.*?(政|领|导|府)|政.*?🐻|领.*?🐻)",
                "score": 0.7,
                "category": "politics"
            },
            
            # 暗语隐喻
            {
                "name": "动物隐喻",
                "pattern": r"(森林之王|动物王国.*?(政策|决策)|自然界.*?领袖)",
                "score": 0.65,
                "category": "metaphor"
            },
            {
                "name": "时间隐喻",
                "pattern": r"(某个时期|那个年代|历史上.*?事件).*?(政治|领导|政策)",
                "score": 0.6,
                "category": "metaphor"
            },
            
            # 格式利用
            {
                "name": "零宽字符",
                "pattern": r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069]",
                "score": 0.9,
                "category": "evasion"
            },
            {
                "name": "特殊空格",
                "pattern": r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]",
                "score": 0.7,
                "category": "evasion"
            },
        ]
    
    def analyze(self, text: str, rules: List[Dict] = None) -> Dict:
        """
        分析文本语义
        
        Args:
            text: 待分析文本
            rules: 审核规则列表
        
        Returns:
            {
                "is_sensitive": bool,
                "confidence": float (0-1),
                "matched_patterns": [],
                "context_score": float,
                "sentiment_score": float,
                "details": str
            }
        """
        if not text or not text.strip():
            return {
                "is_sensitive": False,
                "confidence": 0,
                "matched_patterns": [],
                "context_score": 0,
                "sentiment_score": 0,
                "details": "空文本"
            }
        
        # 1. 模式匹配
        matched_patterns = []
        max_pattern_score = 0
        
        for pattern_def in self.sensitive_patterns:
            matches = re.finditer(pattern_def["pattern"], text, re.IGNORECASE)
            for match in matches:
                matched_patterns.append({
                    "name": pattern_def["name"],
                    "matched": match.group(0),
                    "score": pattern_def["score"],
                    "category": pattern_def["category"]
                })
                max_pattern_score = max(max_pattern_score, pattern_def["score"])
        
        # 2. 上下文分析
        context_score = self._analyze_context(text)
        
        # 3. 情感分析
        sentiment_score = self._analyze_sentiment(text)
        
        # 4. 综合评分
        # 加权: 模式40% + 上下文30% + 情感30%
        confidence = (
            max_pattern_score * 0.4 +
            context_score * 0.3 +
            sentiment_score * 0.3
        )
        
        # 如果有明确匹配,提高置信度
        if matched_patterns:
            confidence = max(confidence, max_pattern_score * 0.8)
        
        is_sensitive = confidence >= 0.5
        
        # 生成详细说明
        details = self._generate_details(matched_patterns, context_score, sentiment_score)
        
        return {
            "is_sensitive": is_sensitive,
            "confidence": round(confidence, 3),
            "matched_patterns": matched_patterns[:5],  # 只返回前5个
            "context_score": round(context_score, 3),
            "sentiment_score": round(sentiment_score, 3),
            "details": details
        }
    
    def _analyze_context(self, text: str) -> float:
        """分析上下文语境"""
        score = 0.0
        
        # 检查是否包含政治相关词汇
        politics_count = 0
        for keyword in self.context_keywords["政治"]:
            if keyword in text:
                politics_count += 1
        
        if politics_count >= 2:
            score += 0.4
        elif politics_count == 1:
            score += 0.2
        
        # 检查是否试图伪装成其他话题
        other_context = False
        for category in ["经济", "社会"]:
            for keyword in self.context_keywords[category]:
                if keyword in text:
                    other_context = True
                    break
        
        # 如果同时包含政治词汇和其他话题,可能是伪装
        if politics_count > 0 and other_context:
            score += 0.3
        
        return min(score, 1.0)
    
    def _analyze_sentiment(self, text: str) -> float:
        """分析情感倾向"""
        negative_count = sum(1 for word in self.negative_words if word in text)
        positive_count = sum(1 for word in self.positive_words if word in text)
        
        # 负面情感比例
        total = negative_count + positive_count
        if total == 0:
            return 0.0
        
        negative_ratio = negative_count / total
        
        # 负面情感越多,风险越高
        if negative_ratio > 0.7:
            return 0.8
        elif negative_ratio > 0.5:
            return 0.6
        elif negative_ratio > 0.3:
            return 0.4
        else:
            return 0.2
    
    def _generate_details(
        self, 
        patterns: List[Dict], 
        context: float, 
        sentiment: float
    ) -> str:
        """生成详细说明"""
        parts = []
        
        if patterns:
            pattern_names = [p["name"] for p in patterns[:3]]
            parts.append(f"匹配模式: {', '.join(pattern_names)}")
        
        if context > 0.5:
            parts.append("上下文可疑")
        
        if sentiment > 0.6:
            parts.append("负面情感明显")
        
        return "; ".join(parts) if parts else "未检测到明显风险"
    
    def batch_analyze(self, texts: List[str], rules: List[Dict] = None) -> List[Dict]:
        """批量分析"""
        return [self.analyze(text, rules) for text in texts]


# 全局实例
SEMANTIC_ANALYZER = SemanticAnalyzer()


# 兼容旧接口
def analyze_semantic(text: str, rules: List[Dict] = None) -> Dict:
    """分析文本语义(兼容函数)"""
    return SEMANTIC_ANALYZER.analyze(text, rules)
