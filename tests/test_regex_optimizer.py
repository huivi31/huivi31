# -*- coding: utf-8 -*-
"""
正则优化器测试
"""

import unittest

from regex_optimizer import RegexOptimizer, RegexPatternCompiler


class TestRegexPatternCompiler(unittest.TestCase):
    """正则模式编译器测试"""
    
    def setUp(self):
        self.compiler = RegexPatternCompiler()
    
    def test_build_keyword_pattern(self):
        """测试关键词模式构建"""
        keywords = ["政治", "经济", "文化"]
        pattern = self.compiler.build_keyword_pattern(keywords)
        
        self.assertIsNotNone(pattern)
        
        # 测试匹配
        text1 = "这是关于政治的讨论"
        self.assertTrue(pattern.search(text1))
        
        text2 = "这是普通内容"
        self.assertIsNone(pattern.search(text2))
    
    def test_build_fuzzy_pattern(self):
        """测试模糊匹配模式"""
        words = ["敏感词"]
        pattern = self.compiler.build_fuzzy_pattern(words)
        
        self.assertIsNotNone(pattern)
        
        # 测试匹配带空格的变体
        text1 = "敏 感 词"
        self.assertTrue(pattern.search(text1))
        
        text2 = "敏*感*词"
        self.assertTrue(pattern.search(text2))


class TestRegexOptimizer(unittest.TestCase):
    """正则优化器测试"""
    
    def setUp(self):
        self.optimizer = RegexOptimizer()
        
        # 初始化测试规则
        rules = [
            {
                "id": "R001",
                "keywords": ["政治", "经济", "军事"]
            },
            {
                "id": "R002",
                "keywords": ["敏感", "禁止"]
            }
        ]
        self.optimizer.initialize(rules)
    
    def test_quick_scan_match(self):
        """测试快速扫描 - 有匹配"""
        text = "这是关于政治的讨论"
        result = self.optimizer.quick_scan(text)
        
        self.assertTrue(result['has_match'])
        self.assertIn("政治", result['matched_keywords'])
        self.assertGreater(result['match_count'], 0)
    
    def test_quick_scan_no_match(self):
        """测试快速扫描 - 无匹配"""
        text = "这是普通的内容"
        result = self.optimizer.quick_scan(text)
        
        self.assertFalse(result['has_match'])
        self.assertEqual(len(result['matched_keywords']), 0)
    
    def test_detailed_match(self):
        """测试详细匹配"""
        text = "政治和经济都是重要话题"
        keywords = ["政治", "经济", "文化"]
        
        result = self.optimizer.detailed_match(text, keywords)
        
        self.assertIn("政治", result['matched'])
        self.assertIn("经济", result['matched'])
        self.assertNotIn("文化", result['matched'])
        self.assertGreater(result['confidence'], 0)
    
    def test_get_stats(self):
        """测试统计信息"""
        stats = self.optimizer.get_stats()
        
        self.assertTrue(stats['initialized'])
        self.assertGreater(stats['keyword_patterns'], 0)


if __name__ == '__main__':
    unittest.main()
