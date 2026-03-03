# -*- coding: utf-8 -*-
"""
L3 正则表达式优化器
v2.3.0 - 将常见模式编译为高性能正则表达式

性能目标：在L2基础上再提升3-5倍（总体400-1000倍提升）
"""

import re
from typing import List, Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


class RegexPatternCompiler:
    """
    正则模式编译器
    将敏感词和规则编译成高效的正则表达式
    """
    
    def __init__(self):
        self.compiled_patterns: Dict[str, re.Pattern] = {}
        self._pattern_cache: Dict[str, List[str]] = {}
    
    def build_keyword_pattern(self, keywords: List[str]) -> re.Pattern:
        """
        构建关键词匹配正则
        
        Args:
            keywords: 关键词列表
        
        Returns:
            编译后的正则表达式
        """
        if not keywords:
            return re.compile(r"(?!.*)")  # 永不匹配
        
        # 缓存键
        cache_key = "|".join(sorted(keywords))
        if cache_key in self.compiled_patterns:
            return self.compiled_patterns[cache_key]
        
        # 转义特殊字符
        escaped = [re.escape(kw) for kw in keywords]
        
        # 构建正则：\b(keyword1|keyword2|...)\b
        # 使用word boundary确保精确匹配
        pattern_str = r"\b(" + "|".join(escaped) + r")\b"
        
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            self.compiled_patterns[cache_key] = pattern
            return pattern
        except re.error as e:
            logger.error(f"Failed to compile pattern: {e}")
            # 降级：逐个匹配
            return None
    
    def build_fuzzy_pattern(self, base_words: List[str]) -> re.Pattern:
        """
        构建模糊匹配正则（处理空格/符号分隔）
        
        Args:
            base_words: 基础词列表
        
        Returns:
            编译后的正则表达式
        """
        if not base_words:
            return re.compile(r"(?!.*)")
        
        cache_key = f"fuzzy:{','.join(sorted(base_words))}"
        if cache_key in self.compiled_patterns:
            return self.compiled_patterns[cache_key]
        
        patterns = []
        for word in base_words:
            # 为每个字符间添加可选的空格/符号
            # 例如: "敏感" -> "敏[\\s\\*\\-_]*感"
            chars = list(word)
            fuzzy_word = "[\\s\\*\\-_\\.]*".join(re.escape(c) for c in chars)
            patterns.append(fuzzy_word)
        
        pattern_str = "(" + "|".join(patterns) + ")"
        
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            self.compiled_patterns[cache_key] = pattern
            return pattern
        except re.error as e:
            logger.error(f"Failed to compile fuzzy pattern: {e}")
            return None
    
    def build_homophone_pattern(self, word: str, homophones: List[str]) -> re.Pattern:
        """
        构建谐音匹配正则
        
        Args:
            word: 原词
            homophones: 谐音列表
        
        Returns:
            编译后的正则表达式
        """
        if not homophones:
            return None
        
        cache_key = f"homo:{word}"
        if cache_key in self.compiled_patterns:
            return self.compiled_patterns[cache_key]
        
        all_variants = [word] + homophones
        escaped = [re.escape(v) for v in all_variants]
        pattern_str = r"\b(" + "|".join(escaped) + r")\b"
        
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            self.compiled_patterns[cache_key] = pattern
            return pattern
        except re.error:
            return None
    
    def clear_cache(self):
        """清空缓存"""
        self.compiled_patterns.clear()
        self._pattern_cache.clear()


class RegexOptimizer:
    """
    L3 正则优化引擎
    使用预编译的正则表达式进行高速匹配
    """
    
    def __init__(self):
        self.compiler = RegexPatternCompiler()
        
        # 预编译的模式集合
        self.keyword_patterns: Dict[str, re.Pattern] = {}
        self.fuzzy_patterns: Dict[str, re.Pattern] = {}
        self.homophone_patterns: Dict[str, re.Pattern] = {}
        
        # 特殊模式
        self.special_patterns = {
            "url": re.compile(r"https?://[^\s]+"),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(r"\b1[3-9]\d{9}\b"),
            "emoji": re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]"),
        }
        
        self._initialized = False
    
    def initialize(self, rules: List[Dict]):
        """
        初始化正则模式
        
        Args:
            rules: 规则列表
        """
        logger.info(f"Initializing L3 Regex Optimizer with {len(rules)} rules")
        
        # 收集所有关键词
        all_keywords = set()
        fuzzy_words = set()
        
        for rule in rules:
            keywords = rule.get("keywords", [])
            for kw in keywords:
                if len(kw) >= 2:
                    all_keywords.add(kw)
                    if len(kw) >= 3:  # 长词用模糊匹配
                        fuzzy_words.add(kw)
        
        # 编译关键词模式
        if all_keywords:
            self.keyword_patterns["main"] = self.compiler.build_keyword_pattern(
                list(all_keywords)
            )
        
        # 编译模糊匹配模式
        if fuzzy_words:
            self.fuzzy_patterns["main"] = self.compiler.build_fuzzy_pattern(
                list(fuzzy_words)
            )
        
        self._initialized = True
        logger.info("L3 Regex Optimizer initialized successfully")
    
    def quick_scan(self, text: str) -> Dict:
        """
        快速扫描文本
        
        Args:
            text: 待检测文本
        
        Returns:
            {
                "has_match": bool,
                "matched_keywords": List[str],
                "match_count": int,
                "patterns_matched": List[str]
            }
        """
        if not self._initialized:
            return {
                "has_match": False,
                "matched_keywords": [],
                "match_count": 0,
                "patterns_matched": []
            }
        
        matched_keywords = set()
        patterns_matched = []
        
        # 1. 关键词精确匹配
        keyword_pattern = self.keyword_patterns.get("main")
        if keyword_pattern:
            matches = keyword_pattern.findall(text)
            if matches:
                matched_keywords.update(matches)
                patterns_matched.append("keyword")
        
        # 2. 模糊匹配
        fuzzy_pattern = self.fuzzy_patterns.get("main")
        if fuzzy_pattern:
            matches = fuzzy_pattern.findall(text)
            if matches:
                patterns_matched.append("fuzzy")
        
        # 3. 特殊模式检测
        for pattern_name, pattern in self.special_patterns.items():
            if pattern.search(text):
                patterns_matched.append(pattern_name)
        
        return {
            "has_match": len(matched_keywords) > 0 or len(patterns_matched) > 0,
            "matched_keywords": list(matched_keywords),
            "match_count": len(matched_keywords),
            "patterns_matched": patterns_matched
        }
    
    def detailed_match(self, text: str, keywords: List[str]) -> Dict:
        """
        详细匹配（用于确认）
        
        Args:
            text: 文本
            keywords: 待匹配的关键词列表
        
        Returns:
            {
                "matched": List[str],
                "positions": List[tuple],  # (start, end, keyword)
                "confidence": float
            }
        """
        matched = []
        positions = []
        
        # 构建临时正则
        pattern = self.compiler.build_keyword_pattern(keywords)
        if not pattern:
            # 降级到字符串匹配
            text_lower = text.lower()
            for kw in keywords:
                if kw.lower() in text_lower:
                    matched.append(kw)
        else:
            # 使用正则查找所有匹配
            for match in pattern.finditer(text):
                matched.append(match.group())
                positions.append((match.start(), match.end(), match.group()))
        
        # 计算置信度
        confidence = min(1.0, len(matched) / max(1, len(keywords)))
        
        return {
            "matched": list(set(matched)),
            "positions": positions,
            "confidence": confidence
        }
    
    def update_rules(self, rules: List[Dict]):
        """
        更新规则（重新初始化）
        
        Args:
            rules: 新规则列表
        """
        self.compiler.clear_cache()
        self.keyword_patterns.clear()
        self.fuzzy_patterns.clear()
        self.homophone_patterns.clear()
        self.initialize(rules)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "initialized": self._initialized,
            "keyword_patterns": len(self.keyword_patterns),
            "fuzzy_patterns": len(self.fuzzy_patterns),
            "homophone_patterns": len(self.homophone_patterns),
            "cached_patterns": len(self.compiler.compiled_patterns)
        }


# 全局实例
regex_optimizer = RegexOptimizer()


def get_regex_optimizer() -> RegexOptimizer:
    """获取正则优化器实例"""
    return regex_optimizer
