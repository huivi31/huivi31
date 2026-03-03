"""
知识提取引擎
v1.0 - 使用LLM从原始情报中提取结构化攻击技术

核心功能：
1. 从情报中提取攻击技术
2. 生成结构化知识
3. 评估技术价值
4. 创造性地组合新技术
"""

import google.generativeai as genai
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class KnowledgeExtractionEngine:
    """
    知识提取引擎
    
    使用Gemini LLM深度分析情报，提取可操作的攻击技术
    """
    
    def __init__(self, api_key: str = None):
        """
        初始化知识提取引擎
        
        Args:
            api_key: Gemini API密钥
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        logger.info("✅ 知识提取引擎初始化完成")
    
    def extract_from_intelligence(self, intelligence: Dict) -> Optional[Dict]:
        """
        从单条情报中提取攻击技术
        
        Args:
            intelligence: 情报字典
            
        Returns:
            提取的攻击技术，如果无法提取则返回None
        """
        prompt = self._build_extraction_prompt(intelligence)
        
        try:
            logger.info(f"🔍 正在分析情报: {intelligence['title'][:50]}...")
            
            response = self.model.generate_content(prompt)
            
            # 解析JSON响应
            technique = self._parse_llm_response(response.text)
            
            if technique:
                # 添加元数据
                technique['source_intelligence'] = {
                    'title': intelligence['title'],
                    'url': intelligence['url'],
                    'source': intelligence['source'],
                    'collected_at': intelligence['collected_at']
                }
                technique['extracted_at'] = datetime.now().isoformat()
                
                logger.info(f"✅ 提取成功: {technique.get('name', 'Unknown')}")
                return technique
            else:
                logger.warning("❌ LLM未能提取有效技术")
                return None
                
        except Exception as e:
            logger.error(f"❌ 提取失败: {e}")
            return None
    
    def batch_extract(self, intelligence_list: List[Dict]) -> List[Dict]:
        """
        批量提取攻击技术
        
        Args:
            intelligence_list: 情报列表
            
        Returns:
            提取的技术列表
        """
        logger.info(f"📦 开始批量提取 ({len(intelligence_list)} 条情报)...")
        
        techniques = []
        success_count = 0
        fail_count = 0
        
        for idx, intelligence in enumerate(intelligence_list, 1):
            logger.info(f"[{idx}/{len(intelligence_list)}] 处理中...")
            
            technique = self.extract_from_intelligence(intelligence)
            
            if technique:
                techniques.append(technique)
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"📊 批量提取完成: 成功 {success_count}, 失败 {fail_count}")
        return techniques
    
    def synthesize_new_techniques(self, 
                                  existing_techniques: List[Dict],
                                  new_intelligence: List[Dict],
                                  count: int = 3) -> List[Dict]:
        """
        综合创造新技术
        
        基于现有技术库和最新情报，创造性地提出新的攻击变种
        
        Args:
            existing_techniques: 现有技术库
            new_intelligence: 最新情报
            count: 生成数量
            
        Returns:
            新技术列表
        """
        logger.info(f"🧠 开始创造性综合 (目标: {count} 个新技术)...")
        
        prompt = self._build_synthesis_prompt(
            existing_techniques[:10],  # 取前10个作为示例
            new_intelligence[:5],      # 取前5条作为灵感
            count
        )
        
        try:
            response = self.model.generate_content(prompt)
            new_techniques = self._parse_synthesis_response(response.text)
            
            logger.info(f"✅ 创造性综合完成: 生成 {len(new_techniques)} 个新技术")
            return new_techniques
            
        except Exception as e:
            logger.error(f"❌ 创造性综合失败: {e}")
            return []
    
    def assess_technique_value(self, technique: Dict) -> float:
        """
        评估技术价值
        
        使用LLM评估攻击技术的实战价值
        
        Args:
            technique: 攻击技术
            
        Returns:
            价值分数 (0.0-1.0)
        """
        prompt = f"""
你是一个资深红队专家。评估以下攻击技术的实战价值。

技术名称：{technique.get('name', 'Unknown')}
技术分类：{technique.get('category', 'Unknown')}
技术描述：{technique.get('description', 'No description')}
检测难度：{technique.get('detection_difficulty', 'Unknown')}/10

请从以下维度评分（0-10分）：
1. **新颖性**: 是否为新技术或新变种
2. **实战性**: 成功率、稳定性、可靠性
3. **隐蔽性**: 对防御系统的绕过能力
4. **影响力**: 潜在危害程度
5. **通用性**: 适用场景广度

输出JSON格式：
{{
    "novelty": 分数,
    "practicality": 分数,
    "stealth": 分数,
    "impact": 分数,
    "versatility": 分数,
    "overall_score": 综合分数(0-10),
    "reasoning": "评分理由（100字内）"
}}
"""
        
        try:
            response = self.model.generate_content(prompt)
            assessment = self._parse_json_response(response.text)
            
            # 归一化到0-1
            score = assessment.get('overall_score', 5.0) / 10.0
            
            logger.info(f"📊 技术评估: {technique.get('name')} -> {score:.2f}")
            return score
            
        except Exception as e:
            logger.warning(f"⚠️ 评估失败，使用默认分数: {e}")
            return 0.5  # 默认中等价值
    
    def _build_extraction_prompt(self, intelligence: Dict) -> str:
        """构建提取prompt"""
        return f"""
你是一个红队安全专家。分析以下情报，提取可用的攻击技术。

【情报信息】
标题：{intelligence['title']}
内容：{intelligence['content'][:2000]}
来源：{intelligence.get('source', 'Unknown')}
类型：{intelligence.get('type', 'Unknown')}

【任务要求】
如果这条情报包含可操作的攻击技术，请提取以下信息：

1. **技术名称**: 简洁明确的名称（不超过20字）
2. **技术分类**: 从以下选择
   - 社会工程学
   - 技术绕过
   - 权限提升
   - 横向移动
   - 数据外泄
   - 其他
3. **技术描述**: 原理说明（100-200字）
4. **关键步骤**: 实施步骤（3-5步）
5. **示例Payload**: 如果有具体的攻击样本或代码
6. **检测难度**: 1-10分（10分最难检测）
7. **适用场景**: 什么情况下使用
8. **防御建议**: 如何检测和防御

【输出格式】
严格输出JSON格式（不要markdown代码块标记）：
{{
    "name": "技术名称",
    "category": "分类",
    "description": "描述",
    "steps": ["步骤1", "步骤2", "步骤3"],
    "example_payload": "示例（如果有）",
    "detection_difficulty": 数字,
    "applicable_scenarios": ["场景1", "场景2"],
    "defense_suggestions": ["建议1", "建议2"]
}}

⚠️ 重要：如果情报不包含可操作的攻击技术，输出：{{"name": null}}
"""
    
    def _build_synthesis_prompt(self, 
                                existing: List[Dict],
                                new_intel: List[Dict],
                                count: int) -> str:
        """构建综合prompt"""
        existing_summary = "\n".join([
            f"- {t.get('name', 'Unknown')}: {t.get('description', '')[:100]}"
            for t in existing
        ])
        
        intel_summary = "\n".join([
            f"- {i['title'][:80]}"
            for i in new_intel
        ])
        
        return f"""
你是一个创新的红队研究员。基于现有技术和最新情报，创造性地提出新的攻击变种。

【现有技术库（示例）】
{existing_summary}

【最新情报】
{intel_summary}

【任务】
提出 {count} 种新的攻击技术或变种。要求：
1. 必须新颖（不在现有库中）
2. 必须可行（基于现实技术）
3. 必须有实战价值

对每个新技术，说明：
- 技术名称
- 灵感来源（基于哪些现有技术/情报）
- 创新点
- 实施步骤
- 检测难度

【输出格式】
严格输出JSON数组（不要markdown代码块）：
[
    {{
        "name": "新技术1",
        "category": "分类",
        "description": "描述",
        "inspiration": "灵感来源",
        "innovation": "创新点",
        "steps": ["步骤1", "步骤2"],
        "detection_difficulty": 数字
    }},
    ...
]
"""
    
    def _parse_llm_response(self, text: str) -> Optional[Dict]:
        """解析LLM响应"""
        try:
            # 移除markdown代码块标记
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            data = json.loads(text.strip())
            
            # 检查是否有效
            if data.get('name') is None or data.get('name') == "null":
                return None
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}\n响应: {text[:200]}")
            return None
        except Exception as e:
            logger.error(f"解析失败: {e}")
            return None
    
    def _parse_json_response(self, text: str) -> Dict:
        """解析JSON响应"""
        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            return json.loads(text.strip())
        except:
            return {}
    
    def _parse_synthesis_response(self, text: str) -> List[Dict]:
        """解析综合响应"""
        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            return json.loads(text.strip())
        except:
            return []


# 快速测试
async def test_knowledge_extraction():
    """测试知识提取"""
    print("=" * 60)
    print("🧪 测试知识提取引擎")
    print("=" * 60)
    
    # 1. 初始化引擎
    extractor = KnowledgeExtractionEngine()
    
    # 2. 准备测试情报
    test_intelligence = {
        "title": "Prompt Injection: A New Attack Vector for LLM Applications",
        "content": """
        Recent research has identified a critical vulnerability in Large Language Model (LLM) 
        applications: prompt injection attacks. Attackers can manipulate the system by crafting 
        malicious prompts that override the original instructions. For example, by embedding 
        hidden instructions in user input, an attacker can extract sensitive information or 
        cause the system to perform unauthorized actions. The attack works by exploiting the 
        model's inability to distinguish between trusted instructions and user-provided data.
        """,
        "url": "https://example.com/prompt-injection",
        "source": "research",
        "collected_at": datetime.now().isoformat()
    }
    
    # 3. 提取技术
    print("\n[测试1] 从情报提取攻击技术...")
    technique = extractor.extract_from_intelligence(test_intelligence)
    
    if technique:
        print(f"✅ 提取成功!")
        print(f"   名称: {technique.get('name')}")
        print(f"   分类: {technique.get('category')}")
        print(f"   检测难度: {technique.get('detection_difficulty')}/10")
    else:
        print("❌ 提取失败")
    
    # 4. 评估价值
    if technique:
        print("\n[测试2] 评估技术价值...")
        score = extractor.assess_technique_value(technique)
        print(f"✅ 价值评分: {score:.2f}/1.0")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成")
    print("=" * 60)
    
    return technique


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    
    result = asyncio.run(test_knowledge_extraction())
    
    if result:
        print("\n📋 提取的技术详情:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
