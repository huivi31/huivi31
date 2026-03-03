"""
自进化系统测试脚本
快速演示完整的自进化流程
"""

import asyncio
import os
import sys
from pathlib import Path

# 设置API密钥
os.environ["GEMINI_API_KEY"] = "AIzaSyBQs8YMjD16htU2S9T6nMbPNJj-4QueBeE"

from evolution_engine import EvolutionEngine


async def main():
    print("🚀 自进化攻击系统 - 快速演示")
    print("=" * 70)
    
    # 设置输出目录
    output_dir = "/tmp/evolution_demo"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 初始化进化引擎
    print("\n[1/3] 初始化进化引擎...")
    engine = EvolutionEngine(output_dir=output_dir)
    print("✅ 引擎就绪")
    
    # 运行进化流程
    print("\n[2/3] 执行每日进化流程...")
    print("⏱️  预计时间: 2-3分钟\n")
    
    result = await engine.run_daily_evolution()
    
    # 显示结果
    print("\n[3/3] 进化结果汇总")
    print("=" * 70)
    print(f"📡 情报收集: {result['stages']['intelligence_collection']['total_collected']} 条")
    print(f"   ├─ arXiv论文: {result['stages']['intelligence_collection']['by_source']['arxiv']} 篇")
    print(f"   ├─ GitHub仓库: {result['stages']['intelligence_collection']['by_source']['github']} 个")
    print(f"   ├─ CVE漏洞: {result['stages']['intelligence_collection']['by_source']['cve']} 个")
    print(f"   └─ 安全新闻: {result['stages']['intelligence_collection']['by_source']['news']} 条")
    
    print(f"\n🧠 知识提取: {result['stages']['knowledge_extraction']['extracted_count']} 个攻击技术")
    print(f"📊 平均价值: {result['stages']['value_assessment']['avg_score']:.2f}/1.0")
    print(f"⚡ 高价值技术: {result['stages']['filtering']['high_value_count']} 个")
    
    print(f"\n📁 输出目录: {output_dir}")
    print(f"   ├─ evolution_log_*.json   (进化日志)")
    print(f"   ├─ intelligence_*.json    (原始情报)")
    print(f"   ├─ techniques_*.json      (提取的技术)")
    print(f"   └─ report_*.md            (可读报告)")
    
    print("\n" + "=" * 70)
    print("🎉 演示完成！系统已成功进化")
    print("=" * 70)
    
    # 显示报告预览
    print("\n📋 进化报告预览:")
    report_files = list(Path(output_dir).glob("report_*.md"))
    if report_files:
        latest_report = sorted(report_files)[-1]
        with open(latest_report, "r", encoding="utf-8") as f:
            lines = f.readlines()[:30]  # 前30行
            print("".join(lines))
            print("\n... (完整报告请查看文件)")


if __name__ == "__main__":
    asyncio.run(main())
