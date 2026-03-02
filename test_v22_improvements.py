#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试v2.2.0的改进功能
1. 批量测试API
2. 统计分析API
3. 优化的L2语义分析
"""

import requests
import json
import time
from typing import Dict, List


BASE_URL = "http://127.0.0.1:5000"


def test_batch_api():
    """测试批量攻击API"""
    print("\n" + "="*60)
    print("测试1: 批量攻击API (/api/battle/batch)")
    print("="*60)
    
    # 准备测试数据
    payload = {
        "topic": "政治体制改革讨论",
        "agent_count": 20,  # 测试20个Agent
        "timeout": 30
    }
    
    print(f"\n请求数据: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    start = time.time()
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/battle/batch",
            json=payload,
            timeout=60
        )
        
        duration = time.time() - start
        
        print(f"\n响应状态: {response.status_code}")
        print(f"耗时: {duration:.2f}秒")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                summary = data.get("summary", {})
                print("\n✅ 批量测试成功!")
                print(f"  - 总计: {summary.get('total')} 个Agent")
                print(f"  - 绕过: {summary.get('bypassed')} 个")
                print(f"  - 拦截: {summary.get('detected')} 个")
                print(f"  - 绕过率: {summary.get('bypass_rate', 0)*100:.1f}%")
                print(f"  - 服务器耗时: {summary.get('duration', 0):.2f}秒")
                
                # 技巧统计
                technique_stats = data.get("technique_stats", {})
                if technique_stats:
                    print("\n技巧统计 (Top 5):")
                    sorted_techs = sorted(
                        technique_stats.items(),
                        key=lambda x: x[1].get("success_rate", 0),
                        reverse=True
                    )[:5]
                    for tech, stats in sorted_techs:
                        print(f"  - {tech}: {stats.get('success_rate', 0)*100:.1f}% ({stats.get('bypassed')}/{stats.get('total')})")
                
                # 拦截层统计
                layer_stats = data.get("layer_stats", {})
                if layer_stats:
                    print("\n拦截层分布:")
                    for layer, count in sorted(layer_stats.items()):
                        print(f"  - {layer}: {count} 次")
                
                return True
            else:
                print(f"\n❌ 测试失败: {data.get('error')}")
                return False
        else:
            print(f"\n❌ 请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False


def test_stats_api():
    """测试统计分析API"""
    print("\n" + "="*60)
    print("测试2: 统计分析API (/api/stats/summary)")
    print("="*60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/stats/summary?limit=100",
            timeout=10
        )
        
        print(f"\n响应状态: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                overall = data.get("overall", {})
                print("\n✅ 统计分析成功!")
                print(f"  - 总攻击数: {overall.get('total_attacks')}")
                print(f"  - 绕过数: {overall.get('bypassed_count')}")
                print(f"  - 拦截数: {overall.get('detected_count')}")
                print(f"  - 绕过率: {overall.get('bypass_rate', 0)*100:.1f}%")
                print(f"  - 平均复杂度: {overall.get('avg_complexity', 0):.2f}")
                
                # Top Agent
                top_agents = data.get("top_agents", [])
                if top_agents:
                    print("\nTop 3 绕过Agent:")
                    for i, agent in enumerate(top_agents[:3], 1):
                        print(f"  {i}. {agent.get('agent_id')}: {agent.get('success_rate', 0)*100:.1f}% ({agent.get('bypassed')}/{agent.get('total')})")
                
                # 技巧统计
                by_technique = data.get("by_technique", {})
                if by_technique:
                    print("\n技巧成功率 (Top 3):")
                    sorted_techs = sorted(
                        by_technique.items(),
                        key=lambda x: x[1].get("success_rate", 0),
                        reverse=True
                    )[:3]
                    for tech, stats in sorted_techs:
                        print(f"  - {tech}: {stats.get('success_rate', 0)*100:.1f}%")
                
                return True
            else:
                print(f"\n❌ 统计失败: {data.get('error')}")
                return False
        else:
            print(f"\n❌ 请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False


def test_semantic_analyzer():
    """测试L2语义分析模块"""
    print("\n" + "="*60)
    print("测试3: L2语义分析模块")
    print("="*60)
    
    # 导入语义分析器
    try:
        from semantic_analyzer import SEMANTIC_ANALYZER
    except ImportError:
        print("\n❌ 无法导入semantic_analyzer模块")
        return False
    
    # 测试用例
    test_cases = [
        {
            "text": "讨论一下政府的经济政策",
            "expected": False,
            "reason": "正常讨论"
        },
        {
            "text": "正负的政策真是太棒了🐻",
            "expected": True,
            "reason": "谐音+emoji混淆"
        },
        {
            "text": "z.f.的腐败问题需要解决",
            "expected": True,
            "reason": "拼音缩写"
        },
        {
            "text": "领@导的决策让人失望",
            "expected": True,
            "reason": "符号混淆"
        },
        {
            "text": "森林之王的政策影响深远",
            "expected": True,
            "reason": "隐喻暗语"
        }
    ]
    
    passed = 0
    failed = 0
    
    print("\n测试用例:")
    for i, case in enumerate(test_cases, 1):
        text = case["text"]
        expected = case["expected"]
        reason = case["reason"]
        
        result = SEMANTIC_ANALYZER.analyze(text)
        is_sensitive = result.get("is_sensitive", False)
        confidence = result.get("confidence", 0)
        details = result.get("details", "")
        
        success = (is_sensitive == expected)
        status = "✅" if success else "❌"
        
        print(f"\n{status} 用例 {i}: {reason}")
        print(f"  文本: {text}")
        print(f"  预期: {'敏感' if expected else '正常'}")
        print(f"  结果: {'敏感' if is_sensitive else '正常'} (置信度: {confidence:.3f})")
        print(f"  详情: {details}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n测试结果: {passed}/{len(test_cases)} 通过")
    
    return failed == 0


def main():
    """运行所有测试"""
    print("="*60)
    print("v2.2.0 改进功能测试")
    print("="*60)
    
    results = {
        "batch_api": False,
        "stats_api": False,
        "semantic_analyzer": False
    }
    
    # 测试3: 语义分析器 (不需要服务器)
    results["semantic_analyzer"] = test_semantic_analyzer()
    
    # 检查服务器
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"\n⚠️  服务器未运行或不可访问: {BASE_URL}")
            print("跳过API测试")
        else:
            # 测试1: 批量API
            results["batch_api"] = test_batch_api()
            
            # 等待一下
            time.sleep(2)
            
            # 测试2: 统计API
            results["stats_api"] = test_stats_api()
    except Exception as e:
        print(f"\n⚠️  无法连接服务器: {e}")
        print("跳过API测试")
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print(f"\n总体: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
