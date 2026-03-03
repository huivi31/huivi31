"""
外部情报爬虫模块
v1.0 - 快速原型版本

提供多种情报源的爬虫实现：
- ArxivCrawler: arXiv安全论文
- SecurityNewsCrawler: 安全新闻
- GithubCrawler: GitHub攻击工具
- CVECrawler: CVE漏洞库
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import json
import logging
import ssl

logger = logging.getLogger(__name__)

# 创建SSL上下文（跳过证书验证 - 仅用于开发/测试）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class ArxivCrawler:
    """arXiv论文爬虫 - 安全与密码学领域"""
    
    def __init__(self):
        self.api_url = "http://export.arxiv.org/api/query"
        self.category = "cs.CR"  # Computer Science - Cryptography and Security
    
    async def fetch(self, max_results: int = 10) -> List[Dict]:
        """
        爬取最新安全论文
        
        Args:
            max_results: 最多返回论文数
            
        Returns:
            论文列表
        """
        params = {
            "search_query": f"cat:{self.category}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        logger.info(f"🔍 开始爬取arXiv论文 (max_results={max_results})...")
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(self.api_url, params=params, timeout=30) as response:
                    xml_data = await response.text()
            
            # 解析XML
            soup = BeautifulSoup(xml_data, 'xml')
            papers = []
            
            for entry in soup.find_all('entry'):
                try:
                    # 提取作者
                    authors = [author.find('name').text for author in entry.find_all('author')]
                    
                    # 提取摘要
                    summary = entry.find('summary').text.strip().replace('\n', ' ')
                    
                    # 提取发布日期
                    published = entry.find('published').text.strip()
                    
                    paper = {
                        "title": entry.find('title').text.strip().replace('\n', ' '),
                        "content": summary,
                        "url": entry.find('id').text.strip(),
                        "authors": authors,
                        "published_date": published,
                        "source": "arxiv",
                        "type": "research",
                        "collected_at": datetime.now().isoformat()
                    }
                    
                    papers.append(paper)
                    
                except Exception as e:
                    logger.warning(f"解析论文条目失败: {e}")
                    continue
            
            logger.info(f"✅ arXiv爬取完成: 收集到 {len(papers)} 篇论文")
            return papers
            
        except asyncio.TimeoutError:
            logger.error("❌ arXiv爬取超时")
            return []
        except Exception as e:
            logger.error(f"❌ arXiv爬取失败: {e}")
            return []


class SecurityNewsCrawler:
    """安全新闻爬虫 - 多个安全媒体源"""
    
    def __init__(self):
        self.sources = [
            {
                "name": "安全客",
                "url": "https://www.anquanke.com/",
                "selector": "article.article-item"
            }
        ]
    
    async def fetch(self, max_results: int = 20) -> List[Dict]:
        """
        爬取安全新闻
        
        Args:
            max_results: 最多返回新闻数
            
        Returns:
            新闻列表
        """
        logger.info(f"🔍 开始爬取安全新闻 (max_results={max_results})...")
        
        all_news = []
        
        for source in self.sources:
            try:
                news = await self._fetch_source(source, max_results)
                all_news.extend(news)
            except Exception as e:
                logger.error(f"❌ 爬取 {source['name']} 失败: {e}")
                continue
        
        logger.info(f"✅ 安全新闻爬取完成: 收集到 {len(all_news)} 条")
        return all_news[:max_results]
    
    async def _fetch_source(self, source: Dict, limit: int) -> List[Dict]:
        """爬取单个新闻源"""
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(source['url'], timeout=30) as response:
                html = await response.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        for article in soup.select(source['selector'])[:limit]:
            try:
                title_elem = article.find('h3') or article.find('h2')
                content_elem = article.find('p')
                link_elem = article.find('a')
                
                if not all([title_elem, link_elem]):
                    continue
                
                articles.append({
                    "title": title_elem.text.strip(),
                    "content": content_elem.text.strip() if content_elem else "",
                    "url": link_elem['href'],
                    "source": source['name'],
                    "type": "news",
                    "collected_at": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"解析文章失败: {e}")
                continue
        
        return articles


class GithubCrawler:
    """GitHub攻击工具爬虫"""
    
    def __init__(self):
        self.api_url = "https://api.github.com/search/repositories"
        self.keywords = ["red-team", "penetration-testing", "exploit", "security-tools"]
    
    async def fetch(self, max_results: int = 20) -> List[Dict]:
        """
        爬取GitHub上的攻击工具仓库
        
        Args:
            max_results: 最多返回仓库数
            
        Returns:
            仓库列表
        """
        logger.info(f"🔍 开始爬取GitHub仓库 (max_results={max_results})...")
        
        all_repos = []
        
        for keyword in self.keywords:
            try:
                repos = await self._search_repos(keyword, max_results // len(self.keywords))
                all_repos.extend(repos)
            except Exception as e:
                logger.error(f"❌ 搜索 '{keyword}' 失败: {e}")
                continue
        
        # 去重（按URL）
        seen_urls = set()
        unique_repos = []
        for repo in all_repos:
            if repo['url'] not in seen_urls:
                seen_urls.add(repo['url'])
                unique_repos.append(repo)
        
        logger.info(f"✅ GitHub爬取完成: 收集到 {len(unique_repos)} 个仓库")
        return unique_repos[:max_results]
    
    async def _search_repos(self, keyword: str, per_page: int) -> List[Dict]:
        """搜索GitHub仓库"""
        params = {
            "q": keyword,
            "sort": "updated",
            "order": "desc",
            "per_page": per_page
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Mozilla/5.0"
        }
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(self.api_url, params=params, headers=headers, timeout=30) as response:
                data = await response.json()
        
        repos = []
        for item in data.get('items', []):
            repos.append({
                "title": item['name'],
                "content": item['description'] or "",
                "url": item['html_url'],
                "stars": item['stargazers_count'],
                "updated_at": item['updated_at'],
                "language": item.get('language', 'Unknown'),
                "source": "github",
                "type": "github",
                "collected_at": datetime.now().isoformat()
            })
        
        return repos


class CVECrawler:
    """CVE漏洞爬虫"""
    
    def __init__(self):
        self.api_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    async def fetch(self, days_back: int = 1, max_results: int = 20) -> List[Dict]:
        """
        爬取最新CVE漏洞
        
        Args:
            days_back: 往前查询天数
            max_results: 最多返回漏洞数
            
        Returns:
            CVE列表
        """
        logger.info(f"🔍 开始爬取CVE漏洞 (days_back={days_back}, max_results={max_results})...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            "resultsPerPage": max_results,
            "lastModStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
            "lastModEndDate": end_date.strftime("%Y-%m-%dT23:59:59.999")
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(self.api_url, params=params, timeout=30) as response:
                    data = await response.json()
            
            cves = []
            
            for item in data.get('vulnerabilities', [])[:max_results]:
                try:
                    cve = item['cve']
                    cve_id = cve['id']
                    
                    # 提取描述
                    descriptions = cve.get('descriptions', [])
                    description = descriptions[0]['value'] if descriptions else "No description"
                    
                    # 提取严重程度
                    metrics = cve.get('metrics', {})
                    severity = "UNKNOWN"
                    score = 0.0
                    
                    if 'cvssMetricV31' in metrics:
                        cvss = metrics['cvssMetricV31'][0]['cvssData']
                        severity = cvss.get('baseSeverity', 'UNKNOWN')
                        score = cvss.get('baseScore', 0.0)
                    
                    cves.append({
                        "title": cve_id,
                        "content": description,
                        "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        "severity": severity,
                        "score": score,
                        "published_date": cve.get('published', ''),
                        "source": "cve",
                        "type": "cve",
                        "collected_at": datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.warning(f"解析CVE条目失败: {e}")
                    continue
            
            logger.info(f"✅ CVE爬取完成: 收集到 {len(cves)} 个漏洞")
            return cves
            
        except asyncio.TimeoutError:
            logger.error("❌ CVE爬取超时")
            return []
        except Exception as e:
            logger.error(f"❌ CVE爬取失败: {e}")
            return []


# 快速测试函数
async def test_crawlers():
    """测试所有爬虫"""
    print("=" * 60)
    print("🧪 开始测试爬虫模块")
    print("=" * 60)
    
    # 测试arXiv爬虫
    print("\n[1/4] 测试 ArxivCrawler...")
    arxiv = ArxivCrawler()
    papers = await arxiv.fetch(max_results=5)
    print(f"✅ 收集到 {len(papers)} 篇论文")
    if papers:
        print(f"示例: {papers[0]['title'][:60]}...")
    
    # 测试GitHub爬虫
    print("\n[2/4] 测试 GithubCrawler...")
    github = GithubCrawler()
    repos = await github.fetch(max_results=5)
    print(f"✅ 收集到 {len(repos)} 个仓库")
    if repos:
        print(f"示例: {repos[0]['title']} ({repos[0]['stars']} ⭐)")
    
    # 测试CVE爬虫
    print("\n[3/4] 测试 CVECrawler...")
    cve = CVECrawler()
    cves = await cve.fetch(days_back=7, max_results=5)
    print(f"✅ 收集到 {len(cves)} 个CVE")
    if cves:
        print(f"示例: {cves[0]['title']} ({cves[0]['severity']})")
    
    # 测试安全新闻爬虫
    print("\n[4/4] 测试 SecurityNewsCrawler...")
    news = SecurityNewsCrawler()
    articles = await news.fetch(max_results=5)
    print(f"✅ 收集到 {len(articles)} 条新闻")
    if articles:
        print(f"示例: {articles[0]['title'][:60]}...")
    
    print("\n" + "=" * 60)
    print("🎉 所有爬虫测试完成！")
    print("=" * 60)
    
    return {
        "arxiv": papers,
        "github": repos,
        "cve": cves,
        "news": articles
    }


if __name__ == "__main__":
    # 快速测试
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(test_crawlers())
    
    # 输出汇总
    print("\n📊 收集汇总:")
    print(f"  - arXiv论文: {len(results['arxiv'])} 篇")
    print(f"  - GitHub仓库: {len(results['github'])} 个")
    print(f"  - CVE漏洞: {len(results['cve'])} 个")
    print(f"  - 安全新闻: {len(results['news'])} 条")
    print(f"  - 总计: {sum(len(v) for v in results.values())} 条情报")
