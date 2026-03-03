"""
进化引擎 v1.0
整合情报收集、知识提取、系统进化的完整流程

核心功能：
1. 协调多个爬虫收集情报
2. 使用LLM提取攻击技术
3. 评估技术价值并筛选
4. 触发系统进化
"""

import asyncio
import json
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from crawlers import ArxivCrawler, GithubCrawler, CVECrawler, SecurityNewsCrawler
from knowledge_extraction import KnowledgeExtractionEngine

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    进化引擎
    
    协调完整的进化流程：
    情报收集 -> 知识提取 -> 价值评估 -> 筛选 -> 进化
    """
    
    def __init__(self, api_key: str = None, output_dir: str = None):
        """
        初始化进化引擎
        
        Args:
            api_key: Gemini API密钥
            output_dir: 输出目录
        """
        # 初始化爬虫
        self.arxiv_crawler = ArxivCrawler()
        self.github_crawler = GithubCrawler()
        self.cve_crawler = CVECrawler()
        self.news_crawler = SecurityNewsCrawler()
        
        # 初始化知识提取器
        self.knowledge_extractor = KnowledgeExtractionEngine(api_key)
        
        # 输出目录
        self.output_dir = Path(output_dir or "/tmp/evolution")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ 进化引擎初始化完成")
    
    async def run_daily_evolution(self) -> Dict:
        """
        执行每日进化流程
        
        Returns:
            进化结果汇总
        """
        logger.info("=" * 60)
        logger.info("🚀 开始每日进化流程")
        logger.info("=" * 60)
        
        evolution_log = {
            "timestamp": datetime.now().isoformat(),
            "stages": {}
        }
        
        # Stage 1: 情报收集
        logger.info("\n[Stage 1/5] 📡 情报收集中...")
        intelligence = await self._collect_intelligence()
        evolution_log["stages"]["intelligence_collection"] = {
            "total_collected": len(intelligence),
            "by_source": {
                "arxiv": len([i for i in intelligence if i["source"] == "arxiv"]),
                "github": len([i for i in intelligence if i["source"] == "github"]),
                "cve": len([i for i in intelligence if i["source"] == "cve"]),
                "news": len([i for i in intelligence if i["source"] == "news"])
            }
        }
        
        # Stage 2: 知识提取
        logger.info("\n[Stage 2/5] 🧠 知识提取中...")
        techniques = self._extract_knowledge(intelligence)
        evolution_log["stages"]["knowledge_extraction"] = {
            "extracted_count": len(techniques)
        }
        
        # Stage 3: 价值评估
        logger.info("\n[Stage 3/5] 📊 价值评估中...")
        scored_techniques = self._assess_techniques(techniques)
        evolution_log["stages"]["value_assessment"] = {
            "total_techniques": len(scored_techniques),
            "avg_score": sum(t["value_score"] for t in scored_techniques) / len(scored_techniques) if scored_techniques else 0
        }
        
        # Stage 4: 筛选高价值技术
        logger.info("\n[Stage 4/5] ⚡ 筛选高价值技术...")
        high_value_techniques = self._filter_high_value(scored_techniques, threshold=0.6)
        evolution_log["stages"]["filtering"] = {
            "high_value_count": len(high_value_techniques),
            "threshold": 0.6
        }
        
        # Stage 5: 保存结果
        logger.info("\n[Stage 5/5] 💾 保存进化结果...")
        self._save_evolution_results(evolution_log, intelligence, high_value_techniques)
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 每日进化流程完成")
        logger.info("=" * 60)
        
        return evolution_log
    
    async def _collect_intelligence(self) -> List[Dict]:
        """
        并发收集所有情报源
        
        Returns:
            情报列表
        """
        # 并发运行所有爬虫
        tasks = [
            self.arxiv_crawler.fetch(max_results=5),
            self.github_crawler.fetch(max_results=5),
            self.cve_crawler.fetch(days_back=7, max_results=5),
            self.news_crawler.fetch(max_results=5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_intelligence = []
        for result in results:
            if isinstance(result, list):
                all_intelligence.extend(result)
            else:
                logger.warning(f"爬虫失败: {result}")
        
        logger.info(f"✅ 情报收集完成: 总计 {len(all_intelligence)} 条")
        return all_intelligence
    
    def _extract_knowledge(self, intelligence_list: List[Dict]) -> List[Dict]:
        """
        从情报中提取攻击技术
        
        Args:
            intelligence_list: 情报列表
            
        Returns:
            提取的技术列表
        """
        techniques = []
        
        for idx, intelligence in enumerate(intelligence_list, 1):
            logger.info(f"  [{idx}/{len(intelligence_list)}] 处理: {intelligence['title'][:50]}...")
            
            try:
                technique = self.knowledge_extractor.extract_from_intelligence(intelligence)
                
                if technique:
                    techniques.append(technique)
                    logger.info(f"    ✅ 提取成功: {technique['name']}")
                else:
                    logger.info(f"    ⏭️  跳过（无可用技术）")
                    
            except Exception as e:
                logger.error(f"    ❌ 提取失败: {e}")
                continue
        
        logger.info(f"✅ 知识提取完成: {len(techniques)}/{len(intelligence_list)}")
        return techniques
    
    def _assess_techniques(self, techniques: List[Dict]) -> List[Dict]:
        """
        评估技术价值
        
        Args:
            techniques: 技术列表
            
        Returns:
            带评分的技术列表
        """
        scored_techniques = []
        
        for idx, technique in enumerate(techniques, 1):
            logger.info(f"  [{idx}/{len(techniques)}] 评估: {technique['name']}")
            
            try:
                score = self.knowledge_extractor.assess_technique_value(technique)
                technique["value_score"] = score
                scored_techniques.append(technique)
                logger.info(f"    ✅ 分数: {score:.2f}")
                
            except Exception as e:
                logger.error(f"    ❌ 评估失败: {e}")
                technique["value_score"] = 0.5  # 默认分数
                scored_techniques.append(technique)
        
        logger.info(f"✅ 价值评估完成")
        return scored_techniques
    
    def _filter_high_value(self, techniques: List[Dict], threshold: float = 0.6) -> List[Dict]:
        """
        筛选高价值技术
        
        Args:
            techniques: 技术列表
            threshold: 价值阈值
            
        Returns:
            高价值技术列表
        """
        high_value = [t for t in techniques if t.get("value_score", 0) >= threshold]
        
        # 按分数排序
        high_value.sort(key=lambda x: x.get("value_score", 0), reverse=True)
        
        logger.info(f"✅ 筛选完成: {len(high_value)}/{len(techniques)} 个高价值技术")
        
        if high_value:
            logger.info(f"   Top技术: {high_value[0]['name']} (分数: {high_value[0]['value_score']:.2f})")
        
        return high_value
    
    def _save_evolution_results(self, 
                                evolution_log: Dict,
                                intelligence: List[Dict],
                                techniques: List[Dict]):
        """
        保存进化结果
        
        Args:
            evolution_log: 进化日志
            intelligence: 原始情报
            techniques: 提取的技术
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存进化日志
        log_path = self.output_dir / f"evolution_log_{timestamp}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(evolution_log, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 进化日志已保存: {log_path}")
        
        # 保存原始情报
        intelligence_path = self.output_dir / f"intelligence_{timestamp}.json"
        with open(intelligence_path, "w", encoding="utf-8") as f:
            json.dump(intelligence, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 原始情报已保存: {intelligence_path}")
        
        # 保存提取的技术
        techniques_path = self.output_dir / f"techniques_{timestamp}.json"
        with open(techniques_path, "w", encoding="utf-8") as f:
            json.dump(techniques, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ 攻击技术已保存: {techniques_path}")
        
        # 生成可读报告
        report_path = self.output_dir / f"report_{timestamp}.md"
        self._generate_markdown_report(report_path, evolution_log, techniques)
        logger.info(f"✅ 进化报告已保存: {report_path}")
    
    def _generate_markdown_report(self, 
                                  path: Path,
                                  log: Dict,
                                  techniques: List[Dict]):
        """生成Markdown格式的进化报告"""
        
        report = f"""# 🤖 每日进化报告

**时间**: {log['timestamp']}

---

## 📊 执行摘要

### Stage 1: 情报收集
- **总计**: {log['stages']['intelligence_collection']['total_collected']} 条
- **arXiv论文**: {log['stages']['intelligence_collection']['by_source']['arxiv']} 篇
- **GitHub仓库**: {log['stages']['intelligence_collection']['by_source']['github']} 个
- **CVE漏洞**: {log['stages']['intelligence_collection']['by_source']['cve']} 个
- **安全新闻**: {log['stages']['intelligence_collection']['by_source']['news']} 条

### Stage 2: 知识提取
- **提取成功**: {log['stages']['knowledge_extraction']['extracted_count']} 个攻击技术

### Stage 3: 价值评估
- **平均分数**: {log['stages']['value_assessment']['avg_score']:.2f}/1.0

### Stage 4: 筛选
- **高价值技术**: {log['stages']['filtering']['high_value_count']} 个
- **筛选阈值**: {log['stages']['filtering']['threshold']}

---

## 🎯 高价值攻击技术

"""
        
        for idx, tech in enumerate(techniques, 1):
            report += f"""
### {idx}. {tech['name']}

**分类**: {tech.get('category', 'Unknown')}  
**价值分数**: {tech.get('value_score', 0):.2f}/1.0  
**检测难度**: {tech.get('detection_difficulty', 'N/A')}/10

**描述**: {tech.get('description', 'N/A')}

**实施步骤**:
"""
            for step_idx, step in enumerate(tech.get('steps', []), 1):
                report += f"{step_idx}. {step}\n"
            
            if tech.get('example_payload'):
                report += f"\n**示例Payload**:\n```\n{tech['example_payload']}\n```\n"
            
            report += f"\n**来源**: [{tech['source_intelligence']['title'][:60]}...]({tech['source_intelligence']['url']})\n"
            report += "\n---\n"
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)


# 快速测试
async def test_evolution_engine():
    """测试完整进化流程"""
    import os
    
    print("=" * 60)
    print("🧪 测试完整进化引擎")
    print("=" * 60)
    
    # 初始化引擎
    api_key = os.getenv("GEMINI_API_KEY")
    output_dir = "/Users/jerryhui/.box/Workspace/output/d72e834e-6c18-46ca-bc2b-73c81e041510/evolution_test"
    
    engine = EvolutionEngine(api_key=api_key, output_dir=output_dir)
    
    # 运行进化流程
    result = await engine.run_daily_evolution()
    
    print("\n" + "=" * 60)
    print("📈 进化结果汇总")
    print("=" * 60)
    print(f"情报收集: {result['stages']['intelligence_collection']['total_collected']} 条")
    print(f"知识提取: {result['stages']['knowledge_extraction']['extracted_count']} 个")
    print(f"高价值技术: {result['stages']['filtering']['high_value_count']} 个")
    print(f"输出目录: {output_dir}")
    
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    result = asyncio.run(test_evolution_engine())
