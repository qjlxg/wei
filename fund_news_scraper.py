import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET

def fetch_rss_feed(url: str, source_name: str) -> List[Dict]:
    """
    获取并解析RSS feed，过滤包含'基金'的条目。
    返回列表：每个条目包含title, link, pubDate, source, summary。
    """
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        items = root.findall('.//item')  # 标准RSS item
        filtered_items = []
        for item in items[:10]:  # 限制10条
            title = item.find('title').text if item.find('title') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
            summary = item.find('description').text if item.find('description') is not None else ''
            
            # 过滤：标题或描述包含'基金'
            if re.search(r'基金', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title.strip(),
                    'link': link.strip(),
                    'pubDate': pub_date.strip() if pub_date else 'N/A',
                    'summary': summary[:200] + '...' if len(summary) > 200 else summary,
                    'source': source_name
                })
        return filtered_items
    except Exception as e:
        print(f"Error fetching RSS {url}: {e}")
        return []

def fetch_web_page(url: str, source_name: str, selector: str) -> List[Dict]:
    """
    抓取网页内容，解析标题、链接、摘要，过滤'基金'关键词。
    selector: CSS选择器，定位文章列表。
    """
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.select(selector)[:10]  # 限制10条
        filtered_items = []
        for item in items:
            title_tag = item.select_one('a') or item
            title = title_tag.get_text(strip=True) if title_tag else ''
            link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else ''
            if not link.startswith('http'):
                link = f"https://{url.split('/')[2]}{link}"  # 补全链接
            
            # 摘要：尝试找描述或正文摘要
            summary_tag = item.select_one('.summary, .desc, p, .content') or item
            summary = summary_tag.get_text(strip=True)[:200] + '...' if summary_tag else ''
            
            # 过滤：标题或摘要包含'基金'
            if re.search(r'基金', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title,
                    'link': link,
                    'pubDate': 'N/A',  # 网页通常无明确时间
                    'summary': summary,
                    'source': source_name
                })
        return filtered_items
    except Exception as e:
        print(f"Error fetching web {url}: {e}")
        return []

def generate_markdown(news_items: List[Dict]) -> str:
    """
    生成Markdown格式的输出。
    """
    md_content = f"# 基金新闻聚合 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    md_content += f"来源：微信公众号、雪球、东方财富、财联社等财经社区（关键词：基金）。总计 {len(news_items)} 条。\n\n"
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

def main():
    # 真实来源配置：基于RSSHub文档和搜索结果
    sources = [
        # 微信公众号：中国基金报 (真实biz ID)
        {
            'url': 'https://rsshub.app/weixin/mp/MzI5MjkxNTk5MQ==',
            'name': '微信-中国基金报',
            'type': 'rss'
        },
        # 雪球：真实基金净值/讨论 (华夏回报基金ID: 519002)
        {
            'url': 'https://rsshub.app/xueqiu/fund/519002',
            'name': '雪球-华夏回报基金',
            'type': 'rss'
        },
        # 东方财富：策略报告 (RSS)
        {
            'url': 'https://rsshub.app/eastmoney/report/strategyreport',
            'name': '东方财富-策略报告',
            'type': 'rss'
        },
        # 东方财富：天天基金用户动态 (真实用户ID示例)
        {
            'url': 'https://rsshub.app/eastmoney/ttjj/user/6551094298949188',
            'name': '东方财富-天天基金用户',
            'type': 'rss'
        },
        # 东方财富：基金焦点新闻 (网页抓取)
        {
            'url': 'http://fund.eastmoney.com/focus/jjzx.html',
            'name': '东方财富-基金焦点',
            'type': 'web',
            'selector': '.newsList li'  # 基于页面结构：新闻列表项
        },
        # 财联社：基金电报
        {
            'url': 'https://rsshub.app/cls/telegraph/fund',
            'name': '财联社-基金电报',
            'type': 'rss'
        },
        # 财联社：基金深度
        {
            'url': 'https://rsshub.app/cls/depth/1110',
            'name': '财联社-基金深度',
            'type': 'rss'
        },
        # 格隆汇：基金首页
        {
            'url': 'https://rsshub.app/gelonghui/home/fund',
            'name': '格隆汇-基金',
            'type': 'rss'
        },
        # 中证网：基金栏目
        {
            'url': 'https://rsshub.app/cs/tzjj',
            'name': '中证网-基金',
            'type': 'rss'
        },
        # 证券时报网：基金文章列表
        {
            'url': 'https://rsshub.app/stcn/article/list/fund',
            'name': '证券时报-基金列表',
            'type': 'rss'
        },
        # 21财经：赢基金频道
        {
            'url': 'https://rsshub.app/21caijing/channel/证券/赢基金',
            'name': '21财经-赢基金',
            'type': 'rss'
        },
        # 雪球：基金搜索热帖 (网页)
        {
            'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91',
            'name': '雪球-基金搜索',
            'type': 'web',
            'selector': '.search-result .title a'  # 基于雪球搜索结果列表
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
    
    # 去重（基于链接）
    unique_news = []
    seen_links = set()
    for news in all_news:
        if news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
    
    # 生成Markdown
    md_content = generate_markdown(unique_news)
    output_file = 'fund_news.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。结果保存至 {output_file}")
    
    # 打印前5条示例
    print("\n前5条示例：")
    for i, news in enumerate(unique_news[:5]):
        print(f"{i+1}. [{news['source']}] {news['title']} ({news['pubDate']})")
        print(f"   链接: {news['link']}")
        print(f"   摘要: {news['summary']}\n")

if __name__ == "__main__":
    main()
