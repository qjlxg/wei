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
    获取并解析RSS feed，过滤包含'基金'的条目。
    - 增加更精细的异常处理。
    - 增加时间格式化和摘要清理。
    """
    filtered_items = []
    try:
        # 增强请求头，提高成功率
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # 尝试从响应内容中解析XML
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            print(f"[{source_name}] Error parsing XML. Trying content decoding...")
            # 尝试使用响应的文本内容，以防编码问题
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
            
            # 针对“实盘观点、经验推荐”关键词的弱匹配（防止过度过滤）
            # 这里的关键词过滤依然使用 '基金'，保持原有逻辑，但在摘要清理上进行增强
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
    抓取网页（专用于雪球），过滤'基金'关键词。
    - 增加更精细的异常处理。
    - 增加摘要清理。
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
        
        # 使用更稳健的 select 方法
        items = soup.select(selector)
        
        for item in items[:limit]:
            # 标题和链接都在 a 标签上
            title_tag = item
            if not title_tag:
                continue
            
            title = title_tag.get_text(strip=True)
            link = title_tag.get('href', '')
            
            # 完善链接
            if link and not link.startswith('http'):
                link = f"https://xueqiu.com{link}"
            
            # 尝试查找摘要
            # 在雪球的搜索结果页，摘要通常在标题周围的兄弟节点
            # 针对雪球帖子内容的不同CSS路径进行组合尝试
            parent = item.parent.parent
            summary_tag = parent.select_one('.search-summary, .search-snippet, .search-content')
            
            summary_raw = summary_tag.get_text(strip=True) if summary_tag else title
            
            # 增强摘要长度
            summary = clean_html_summary(summary_raw, max_len=400)
            
            # 针对“实盘观点、经验推荐”关键词的弱匹配
            if re.search(r'基金|实盘|观点|经验|推荐|策略', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title,
                    'link': link if link else 'N/A',
                    'pubDate': 'N/A', # Web抓取通常难获取时间，保持 N/A
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

def generate_markdown(news_items: List[Dict]) -> str:
    """
    生成Markdown。
    """
    md_content = f"# 基金新闻聚合 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    # 使用配置列表来生成来源说明，使其与 main() 函数解耦
    # 动态获取当前配置的来源
    configured_sources = list(set([s['name'].split('-')[0] for s in globals().get('sources', [])]))
    source_names = "、".join(configured_sources)
    md_content += f"来源：{source_names}（关键词：基金/实盘/观点/经验/推荐/策略）。总计 {len(news_items)} 条。\n\n"
    
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

# --- 数据源配置外部化 ---
proxy_base = 'https://rsshub.rss.zgdnz.cc'
# 增加一个更宽泛的雪球搜索，以及对原有来源的关键词过滤增强。
sources = [
    # 财联社-基金电报 (关键词过滤增强)
    {
        'url': f'{proxy_base}/cls/telegraph/fund',
        'name': '财联社-基金电报',
        'type': 'rss'
    },
    # 东方财富-策略报告 (关键词过滤增强)
    {
        'url': f'{proxy_base}/eastmoney/report/strategyreport',
        'name': '东方财富-策略报告',
        'type': 'rss'
    },
    # 格隆汇-基金 (关键词过滤增强)
    {
        'url': f'{proxy_base}/gelonghui/home/fund',
        'name': '格隆汇-基金',
        'type': 'rss'
    },
    # 证券时报-基金列表 (关键词过滤增强)
    {
        'url': f'{proxy_base}/stcn/article/list/fund',
        'name': '证券时报-基金列表',
        'type': 'rss'
    },
    # 21财经-赢基金 (关键词过滤增强)
    {
        'url': f'{proxy_base}/21caijing/channel/%E8%AF%81%E5%88%B8/%E8%B5%A2%E5%9F%BA%E9%87%91',
        'name': '21财经-赢基金',
        'type': 'rss'
    },
    # 雪球-基金搜索 (Web) - 使用更宽泛的关键词组合
    {
        'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91%20%E8%A7%82%E7%82%B9%20%E5%AE%9E%E7%9B%98%20%E7%AD%96%E7%95%A5', # 基金 观点 实盘 策略
        'name': '雪球-实盘观点',
        'type': 'web',
        # 针对雪球搜索结果页的标题链接
        'selector': '.search__list .search-result-item .search-title a' 
    }
]

def main():
    """主执行函数，协调抓取、去重和文件生成。"""
    all_news = []
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取基金新闻 (已扩展关键词和深度)...")
    
    for source in sources:
        print(f"处理来源: {source['name']} ({source['url']})")
        if source['type'] == 'rss':
            # RSS 源默认抓取 15 条
            items = fetch_rss_feed(source['url'], source['name'], limit=15)
        else:
            # Web 源默认抓取 15 条
            items = fetch_web_page(source['url'], source['name'], source.get('selector'), limit=15)
        all_news.extend(items)
    
    # 去重
    unique_news = []
    seen_links = set()
    for news in all_news:
        if news['link'] and news['link'] != 'N/A' and news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
        # 针对链接为 'N/A' 的项目，如果标题和来源相同也去重 (保守策略)
        elif news['link'] == 'N/A' and (news['title'], news['source']) not in seen_links:
             seen_links.add((news['title'], news['source']))
             unique_news.append(news)

    # 排序：按时间倒序排列 (如果时间是'N/A'，则排在最后)
    def sort_key(item):
        # 尝试将时间字符串转换为 datetime 对象
        time_str = item['pubDate']
        if time_str and time_str != 'N/A':
            try:
                # 再次解析为 datetime 对象进行排序
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        # 无法解析或为'N/A'的，返回一个极早的时间，确保排在末尾
        return datetime(1900, 1, 1)

    unique_news.sort(key=sort_key, reverse=True)
    
    # 生成MD
    md_content = generate_markdown(unique_news)
    output_file = 'fund_news_expanded.md' # 更改文件名以区分
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻 (已包含观点/经验关键词)。结果保存至 {output_file}")
    
    # 示例
    print("\n前5条示例：")
    for i, news in enumerate(unique_news[:5]):
        print(f"{i+1}. [{news['source']}] {news['title']} (时间: {news['pubDate']})")
        print(f"    摘要: {news['summary'][:150]}...\n")

if __name__ == "__main__":
    main()
