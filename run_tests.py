#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行所有测试
v2.3.0
"""

import sys
import unittest
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_all_tests():
    """运行所有测试"""
    # 发现所有测试
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出汇总
    print("\n" + "="*70)
    print("测试汇总")
    print("="*70)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    # 计算覆盖率（简单估算）
    if result.testsRun > 0:
        coverage = ((result.testsRun - len(result.failures) - len(result.errors)) 
                   / result.testsRun * 100)
        print(f"通过率: {coverage:.1f}%")
    
    return result.wasSuccessful()


def run_specific_test(test_name: str):
    """运行指定测试"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f"tests.{test_name}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 运行指定测试
        test_name = sys.argv[1]
        print(f"运行测试: {test_name}")
        success = run_specific_test(test_name)
    else:
        # 运行所有测试
        print("运行所有测试...")
        success = run_all_tests()
    
    sys.exit(0 if success else 1)
