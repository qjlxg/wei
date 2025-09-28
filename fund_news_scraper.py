import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET
from dateutil import parser
import pytz

# --- 辅助函数：时间解析和格式化 ---
def parse_and_format_time(pub_date: str) -> str:
    """解析时间字符串，转换为北京时间并格式化。"""
    if pub_date == 'N/A' or not pub_date:
        return 'N/A'
    try:
        # 尝试解析时间
        # 强制设置时区为 UTC (如果pub_date中没有时区信息，但通常RSS feed会提供)
        dt_utc = parser.parse(pub_date).replace(tzinfo=pytz.utc)
        # 转换为北京时间（Asia/Shanghai，UTC+8）
        dt_local = dt_utc.astimezone(pytz.timezone('Asia/Shanghai'))
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        # 解析失败则返回原字符串
        return pub_date

# --- 辅助函数：HTML清理和摘要处理 ---
def clean_html_summary(summary: str, max_len: int = 400) -> str:
    """清理摘要中的HTML标签和多余空格，并进行截断。"""
    if not summary:
        return '无摘要'
    
    # 1. 使用 BeautifulSoup 清理 HTML 标签
    clean_soup = BeautifulSoup(summary, 'html.parser')
    clean_text = clean_soup.get_text(strip=True)
    
    # 2. 清理多余的空白字符和换行
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    # 3. 截断 (将截断长度增加到 400，以捕获更多观点信息)
    if len(clean_text) > max_len:
        return clean_text[:max_len] + '...'
    return clean_text

# --- 核心抓取函数：RSS ---
def fetch_rss_feed(url: str, source_name: str, limit: int = 15) -> List[Dict]: # 扩展抓取数量到 15
    """
    获取并解析RSS feed，过滤包含'基金'、'实盘'、'观点'等关键词的条目。
    """
    filtered_items = []
    try:
        # 增强请求头，提高成功率
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            print(f"[{source_name}] Error parsing XML. Trying content decoding...")
            root = ET.fromstring(response.text.encode('utf-8'))


        items = root.findall('.//item')
        
        for item in items[:limit]:
            title = item.find('title').text if item.find('title') is not None and item.find('title').text else ''
            link = item.find('link').text if item.find('link') is not None and item.find('link').text else 'N/A'
            pub_date_raw = item.find('pubDate').text if item.find('pubDate') is not None and item.find('pubDate').text else 'N/A'
            summary_raw = item.find('description').text if item.find('description') is not None and item.find('description').text else ''
            
            # 清理摘要 (增加摘要长度以捕获更多实盘观点和经验)
            summary = clean_html_summary(summary_raw, max_len=400)
            
            # 格式化时间
            pub_date = parse_and_format_time(pub_date_raw)
            
            # 关键词过滤增强，覆盖：基金、实盘、观点、经验、推荐、策略
            if re.search(r'基金|实盘|观点|经验|推荐|策略', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title.strip(),
                    'link': link.strip(),
                    'pubDate': pub_date,
                    'summary': summary,
                    'source': source_name
                })
        return filtered_items
        
    except requests.exceptions.Timeout:
        print(f"[{source_name}] Error fetching RSS {url}: Request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"[{source_name}] Error fetching RSS {url}: Network or HTTP error: {e}")
    except Exception as e:
        print(f"[{source_name}] Error fetching RSS {url}: An unexpected error occurred: {e}")
    return []

# --- 核心抓取函数：Web (雪球) ---
def fetch_web_page(url: str, source_name: str, selector: str, limit: int = 15) -> List[Dict]: # 扩展抓取数量到 15
    """
    抓取网页（专用于雪球），过滤'基金'、'实盘'等关键词。
    """
    filtered_items = []
    try:
        # 增强请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://xueqiu.com/'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        items = soup.select(selector)
        
        for item in items[:limit]:
            title_tag = item
            if not title_tag:
                continue
            
            title = title_tag.get_text(strip=True)
            link = title_tag.get('href', '')
            
            if link and not link.startswith('http'):
                link = f"https://xueqiu.com{link}"
            
            parent = item.parent.parent
            summary_tag = parent.select_one('.search-summary, .search-snippet, .search-content')
            
            summary_raw = summary_tag.get_text(strip=True) if summary_tag else title
            summary = clean_html_summary(summary_raw, max_len=400)
            
            # 关键词过滤增强
            if re.search(r'基金|实盘|观点|经验|推荐|策略', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title,
                    'link': link if link else 'N/A',
                    'pubDate': 'N/A', 
                    'summary': summary,
                    'source': source_name
                })
        return filtered_items
        
    except requests.exceptions.Timeout:
        print(f"[{source_name}] Error fetching web {url}: Request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"[{source_name}] Error fetching web {url}: Network or HTTP error: {e}")
    except Exception as e:
        print(f"[{source_name}] Error fetching web {url}: An unexpected error occurred: {e}")
    return []

# --- 数据源配置外部化 ---
proxy_base = 'https://rsshub.rss.zgdnz.cc'
sources = [
    # 财联社-基金电报 (RSS)
    {'url': f'{proxy_base}/cls/telegraph/fund', 'name': '财联社-基金电报', 'type': 'rss'},
    # 东方财富-策略报告 (RSS)
    {'url': f'{proxy_base}/eastmoney/report/strategyreport', 'name': '东方财富-策略报告', 'type': 'rss'},
    # 格隆汇-基金 (RSS)
    {'url': f'{proxy_base}/gelonghui/home/fund', 'name': '格隆汇-基金', 'type': 'rss'},
    # 证券时报-基金列表 (RSS)
    {'url': f'{proxy_base}/stcn/article/list/fund', 'name': '证券时报-基金列表', 'type': 'rss'},
    # 21财经-赢基金 (RSS)
    {'url': f'{proxy_base}/21caijing/channel/%E8%AF%81%E5%88%B8/%E8%B5%A2%E5%9F%BA%E9%87%91', 'name': '21财经-赢基金', 'type': 'rss'},
    # 雪球-基金搜索 (Web) - 修复 URL，使用单一关键词
    {
        'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91', # 仅搜索“基金”以提高成功率
        'name': '雪球-基金搜索',
        'type': 'web',
        'selector': '.search__list .search-result-item .search-title a' 
    }
]

def generate_markdown(news_items: List[Dict]) -> str:
    """
    生成Markdown。
    """
    md_content = f"# 基金新闻聚合 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    configured_sources = list(set([s['name'].split('-')[0] for s in globals().get('sources', [])]))
    source_names = "、".join(configured_sources)
    md_content += f"来源：{source_names}（关键词：基金/实盘/观点/经验/推荐/策略）。总计 {len(news_items)} 条。\n\n"
    
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

def main():
    """主执行函数，协调抓取、去重和文件生成。"""
    all_news = []
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取基金新闻 (已扩展关键词和深度)...")
    
    for source in sources:
        print(f"处理来源: {source['name']} ({source['url']})")
        if source['type'] == 'rss':
            items = fetch_rss_feed(source['url'], source['name'], limit=15)
        else:
            items = fetch_web_page(source['url'], source['name'], source.get('selector'), limit=15)
        all_news.extend(items)
    
    # 去重
    unique_news = []
    seen_links = set()
    for news in all_news:
        if news['link'] and news['link'] != 'N/A' and news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
        elif news['link'] == 'N/A' and (news['title'], news['source']) not in seen_links:
             seen_links.add((news['title'], news['source']))
             unique_news.append(news)

    # 排序：按时间倒序排列
    def sort_key(item):
        time_str = item['pubDate']
        if time_str and time_str != 'N/A':
            try:
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return datetime(1900, 1, 1)

    unique_news.sort(key=sort_key, reverse=True)
    
    # 生成MD
    md_content = generate_markdown(unique_news)
    output_file = 'fund_news.md' # 统一文件名
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。结果保存至 {output_file}")
    
    print("\n前5条示例：")
    for i, news in enumerate(unique_news[:5]):
        print(f"{i+1}. [{news['source']}] {news['title']} (时间: {news['pubDate']})")
        print(f"    摘要: {news['summary'][:150]}...\n")

if __name__ == "__main__":
    main()
