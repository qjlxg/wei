import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET

def fetch_rss_feed(url: str, source_name: str) -> List[Dict]:
    """
    获取并解析RSS feed，过滤包含'基金'的条目。
    """
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        items = root.findall('.//item')
        filtered_items = []
        for item in items[:10]:
            title = item.find('title').text if item.find('title') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
            summary = item.find('description').text if item.find('description') is not None else ''
            
            if re.search(r'基金', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title.strip(),
                    'link': link.strip(),
                    'pubDate': pub_date.strip() if pub_date else 'N/A',
                    'summary': (summary[:200] + '...') if len(summary) > 200 else summary,
                    'source': source_name
                })
        return filtered_items
    except Exception as e:
        print(f"Error fetching RSS {url}: {e}")
        return []

def fetch_web_page(url: str, source_name: str, selector: str) -> List[Dict]:
    """
    抓取网页，过滤'基金'关键词。
    """
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.select(selector)[:10]
        filtered_items = []
        for item in items:
            title_tag = item.select_one('a')
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = title_tag['href']
            if not link.startswith('http'):
                link = f"https://xueqiu.com{link}"
            
            summary_tag = item.select_one('.summary, .snippet, .desc')
            summary = summary_tag.get_text(strip=True)[:200] + '...' if summary_tag else title[:200] + '...'
            
            if re.search(r'基金', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title,
                    'link': link,
                    'pubDate': 'N/A',
                    'summary': summary,
                    'source': source_name
                })
        return filtered_items
    except Exception as e:
        print(f"Error fetching web {url}: {e}")
        return []

def generate_markdown(news_items: List[Dict]) -> str:
    """
    生成Markdown。
    """
    md_content = f"# 基金新闻聚合 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    md_content += f"来源：雪球、东方财富、财联社、格隆汇、证券时报、21财经（关键词：基金）。总计 {len(news_items)} 条。\n\n"
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

def main():
    # 工作来源：RSSHub代理 + 雪球Web
    proxy_base = 'https://rsshub.rss.zgdnz.cc'
    sources = [
        # 财联社-基金电报 (测试：返回保险私募基金等)
        {
            'url': f'{proxy_base}/cls/telegraph/fund',
            'name': '财联社-基金电报',
            'type': 'rss'
        },
        # 东方财富-策略报告 (测试：返回公募基金规模等)
        {
            'url': f'{proxy_base}/eastmoney/report/strategyreport',
            'name': '东方财富-策略报告',
            'type': 'rss'
        },
        # 格隆汇-基金 (测试：返回ETF基金流入等)
        {
            'url': f'{proxy_base}/gelonghui/home/fund',
            'name': '格隆汇-基金',
            'type': 'rss'
        },
        # 证券时报-基金列表 (测试：返回公募基金规模突破等)
        {
            'url': f'{proxy_base}/stcn/article/list/fund',
            'name': '证券时报-基金列表',
            'type': 'rss'
        },
        # 21财经-赢基金 (测试：返回余额宝降费等)
        {
            'url': f'{proxy_base}/21caijing/channel/%E8%AF%81%E5%88%B8/%E8%B5%A2%E5%9F%BA%E9%87%91',
            'name': '21财经-赢基金',
            'type': 'rss'
        },
        # 雪球-基金搜索 (Web，调整selector)
        {
            'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91',
            'name': '雪球-基金搜索',
            'type': 'web',
            'selector': '.search-result-item .title a'  # 基于雪球搜索结构
        }
    ]
    
    all_news = []
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取基金新闻...")
    
    for source in sources:
        print(f"处理来源: {source['name']} ({source['url']})")
        if source['type'] == 'rss':
            items = fetch_rss_feed(source['url'], source['name'])
        else:
            items = fetch_web_page(source['url'], source['name'], source['selector'])
        all_news.extend(items)
    
    # 去重
    unique_news = []
    seen_links = set()
    for news in all_news:
        if news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
    
    # 生成MD
    md_content = generate_markdown(unique_news)
    output_file = 'fund_news.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。结果保存至 {output_file}")
    
    # 示例
    print("\n前5条示例：")
    for i, news in enumerate(unique_news[:5]):
        print(f"{i+1}. [{news['source']}] {news['title']}")
        print(f"   摘要: {news['summary'][:100]}...\n")

if __name__ == "__main__":
    main()
