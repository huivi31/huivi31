# -*- coding: utf-8 -*-
"""
异步LLM调用封装
v2.1.0 - 支持并发调用,大幅提升性能
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional
from config import API_CONFIG


class AsyncLLMClient:
    """异步LLM客户端,支持Google Gemini和OpenAI"""
    
    def __init__(self, provider: str = "google", api_key: Optional[str] = None):
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _get_api_key(self) -> str:
        """从配置获取API密钥"""
        if self.provider == "google":
            return API_CONFIG.get("gemini_api_key", "")
        elif self.provider == "openai":
            return API_CONFIG.get("openai_api_key", "")
        return ""
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def generate_async(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 500,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        异步生成文本
        
        Args:
            prompt: 用户提示词
            temperature: 温度参数(0-1+)
            max_tokens: 最大token数
            system_instruction: 系统指令(仅OpenAI支持)
        
        Returns:
            生成的文本
        """
        if self.provider == "google":
            return await self._call_gemini(prompt, temperature, max_tokens)
        elif self.provider == "openai":
            return await self._call_openai(prompt, temperature, max_tokens, system_instruction)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _call_gemini(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """调用Google Gemini API"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                else:
                    error_text = await response.text()
                    return f"[API错误 {response.status}] {error_text[:100]}"
        except asyncio.TimeoutError:
            return "[超时错误] API调用超时"
        except Exception as e:
            return f"[异常错误] {str(e)[:100]}"
    
    async def _call_openai(
        self, 
        prompt: str, 
        temperature: float, 
        max_tokens: int,
        system_instruction: Optional[str]
    ) -> str:
        """调用OpenAI API"""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": API_CONFIG.get("openai_model", "gpt-3.5-turbo"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    error_text = await response.text()
                    return f"[API错误 {response.status}] {error_text[:100]}"
        except asyncio.TimeoutError:
            return "[超时错误] API调用超时"
        except Exception as e:
            return f"[异常错误] {str(e)[:100]}"


async def batch_generate(
    prompts: list[str],
    provider: str = "google",
    temperature: float = 0.7,
    max_workers: int = 10
) -> list[str]:
    """
    批量并发生成文本
    
    Args:
        prompts: 提示词列表
        provider: LLM提供商
        temperature: 温度参数
        max_workers: 最大并发数
    
    Returns:
        生成的文本列表
    """
    semaphore = asyncio.Semaphore(max_workers)
    
    async def generate_with_limit(prompt: str, client: AsyncLLMClient) -> str:
        async with semaphore:
            return await client.generate_async(prompt, temperature)
    
    async with AsyncLLMClient(provider) as client:
        tasks = [generate_with_limit(prompt, client) for prompt in prompts]
        return await asyncio.gather(*tasks)


# 兼容旧版同步接口
def generate_sync(prompt: str, provider: str = "google", temperature: float = 0.7) -> str:
    """同步生成文本(兼容旧代码)"""
    async def _generate():
        async with AsyncLLMClient(provider) as client:
            return await client.generate_async(prompt, temperature)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_generate())
