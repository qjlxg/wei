import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET
from dateutil import parser
import pytz

# --- 【核心配置】分析规则库，可根据新的新闻主题扩展 ---
# 1. 投资线索 (人物/机构 -> 标的/策略)
CLUES_MAP = {
    # 规则: 正则表达式用于匹配新闻内容（标题+摘要）
    r'李蓓|半夏|中证500|IC': '半夏李蓓/中证500/科技成长策略',
    r'国金证券|四中全会|策略月报': '国金证券/四中全会主题策略',
    r'华安证券|成长产业|AI|军工': '华安证券/AI/军工/新成长配置',
    r'开源证券|金股策略|科技|港股': '开源证券/AI+自主可控科技主线',
    r'ETF|股票ETF|百亿俱乐部|吸金': '资金流向/股票ETF/吸金赛道',
    r'贵金属|黄金|避险': '资产对冲/避险配置',
    r'均衡配置|光伏|化工|农业|有色|银行': '均衡策略/低估值轮动配置',
}

# 2. 经验教训 (行为/结果 -> 风险/教训)
LESSONS_MAP = {
    r'跑输大盘|未能满仓|红利板块': '经验教训：新基金建仓策略与市场错配风险',
    r'基金经理|涉赌|免职|内控': '风险提示：基金公司内控和经理道德风险',
    r'机构大举增持|主动权益基金': '机构行为：主动权益基金仍是配置重点',
}

# 3. 行业趋势 (结构变化 -> 行业洞察)
TRENDS_MAP = {
    r'AI|投研|工业化|蚂蚁财富': '行业趋势：投研工业化和AI赋能',
    r'费率|下调|托管费|余额宝': '行业趋势：关注费率成本的长期下行',
    r'私募股权|子公司|广发基金': '行业趋势：头部公募的业务多元化',
    r'量化基金经理|主动基金|一拖多': '行业趋势：量化与主动投资边界模糊',
}
# -----------------------------------------------------------------


# --- 辅助函数：时间解析和格式化 ---
def parse_and_format_time(pub_date: str) -> str:
    """解析时间字符串，转换为北京时间并格式化。"""
    if pub_date == 'N/A' or not pub_date:
        return 'N/A'
    try:
        dt_utc = parser.parse(pub_date).replace(tzinfo=pytz.utc)
        dt_local = dt_utc.astimezone(pytz.timezone('Asia/Shanghai'))
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return pub_date

# --- 辅助函数：HTML清理和摘要处理 ---
def clean_html_summary(summary: str, max_len: int = 400) -> str:
    """清理摘要中的HTML标签和多余空格，并进行截断。"""
    if not summary:
        return '无摘要'
    
    clean_soup = BeautifulSoup(summary, 'html.parser')
    clean_text = clean_soup.get_text(strip=True)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    if len(clean_text) > max_len:
        return clean_text[:max_len] + '...'
    return clean_text

# --- 核心抓取函数：RSS ---
def fetch_rss_feed(url: str, source_name: str, limit: int = 15) -> List[Dict]:
    """获取并解析RSS feed，过滤包含'基金'、'实盘'、'观点'等关键词的条目。"""
    filtered_items = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
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
            
            summary = clean_html_summary(summary_raw, max_len=400)
            pub_date = parse_and_format_time(pub_date_raw)
            
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
def fetch_web_page(url: str, source_name: str, selector: str, limit: int = 15) -> List[Dict]:
    """抓取网页（专用于雪球），过滤'基金'、'实盘'等关键词。"""
    filtered_items = []
    try:
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


# --- 【核心】新闻分析函数：基于规则匹配 ---
def analyze_news(news_items: List[Dict]) -> Dict:
    """
    基于关键词和规则，从新闻列表中提取投资线索和经验教训。
    代码的核心是遍历每条新闻，尝试匹配预定义的正则模式（CLUES_MAP, LESSONS_MAP, TRENDS_MAP）。
    """
    analysis = {
        'investment_clues': [],
        'experience_lessons': [],
        'industry_trends': []
    }

    # 记录已匹配到的分析点，避免重复
    seen_clues = set()
    seen_lessons = set()
    seen_trends = set()

    for item in news_items:
        # 将标题和摘要合并成一个长字符串进行匹配
        text = item['title'] + item['summary']
        
        # 1. 匹配投资线索
        for pattern, focus in CLUES_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and focus not in seen_clues:
                analysis['investment_clues'].append({
                    'focus': focus,
                    'title': item['title'],
                    'link': item['link'],
                })
                seen_clues.add(focus)
                
        # 2. 匹配经验教训
        for pattern, lesson in LESSONS_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and lesson not in seen_lessons:
                analysis['experience_lessons'].append({
                    'lesson': lesson,
                    'title': item['title'],
                    'link': item['link'],
                })
                seen_lessons.add(lesson)

        # 3. 匹配行业趋势
        for pattern, trend in TRENDS_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and trend not in seen_trends:
                analysis['industry_trends'].append({
                    'trend': trend,
                    'title': item['title'],
                    'link': item['link'],
                })
                seen_trends.add(trend)
                
    return analysis

# --- 生成分析报告 ---
def generate_analysis_report(analysis: Dict, total_count: int) -> str:
    """根据分析结果生成结构化 Markdown 报告。"""
    md_report = "\n---\n"
    md_report += "# 📰 基金投资策略分析报告\n\n"
    md_report += f"本报告根据从 {total_count} 条新闻中提取的高价值信息生成，旨在为您提供 **买入指引、风险规避和行业洞察**。\n\n"

    # 1. 投资线索
    md_report += "## 💰 投资线索与市场焦点 (买入指引)\n"
    if analysis['investment_clues']:
        md_report += "| 焦点标的/策略 | 原始标题 (点击查看) |\n"
        md_report += "| :--- | :--- |\n"
        
        for clue in analysis['investment_clues']:
            md_report += f"| **{clue['focus']}** | [{clue['title']}](<{clue['link']}>) |\n"
    else:
        md_report += "暂无明确的投资线索或机构观点被识别。\n"
        
    # 2. 经验与教训
    md_report += "\n## ⚠️ 投资经验与风险规避 (避免踩坑)\n"
    if analysis['experience_lessons']:
        md_report += "| 教训/经验 | 原始标题 (点击查看) |\n"
        md_report += "| :--- | :--- |\n"
        
        for lesson in analysis['experience_lessons']:
            md_report += f"| **{lesson['lesson']}** | [{lesson['title']}](<{lesson['link']}>) |\n"
    else:
        md_report += "暂无明确的经验教训或风险提示被识别。\n"

    # 3. 行业结构与趋势
    md_report += "\n## ✨ 行业结构与未来趋势 (长期洞察)\n"
    if analysis['industry_trends']:
        md_report += "| 行业趋势 | 原始标题 (点击查看) |\n"
        md_report += "| :--- | :--- |\n"
        
        for trend in analysis['industry_trends']:
            md_report += f"| **{trend['trend']}** | [{trend['title']}](<{trend['link']}>) |\n"
    else:
        md_report += "暂无明确的行业趋势或结构变化被识别。\n"

    return md_report


# --- 数据源配置外部化 (保持不变) ---
proxy_base = 'https://rsshub.rss.zgdnz.cc'
sources = [
    {'url': f'{proxy_base}/cls/telegraph/fund', 'name': '财联社-基金电报', 'type': 'rss'},
    {'url': f'{proxy_base}/eastmoney/report/strategyreport', 'name': '东方财富-策略报告', 'type': 'rss'},
    {'url': f'{proxy_base}/gelonghui/home/fund', 'name': '格隆汇-基金', 'type': 'rss'},
    {'url': f'{proxy_base}/stcn/article/list/fund', 'name': '证券时报-基金列表', 'type': 'rss'},
    {'url': f'{proxy_base}/21caijing/channel/%E8%AF%81%E5%88%B8/%E8%B5%A2%E5%9F%BA%E9%87%91', 'name': '21财经-赢基金', 'type': 'rss'},
    {
        'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91',
        'name': '雪球-基金搜索',
        'type': 'web',
        'selector': '.search__list .search-result-item .search-title a' 
    }
]

def generate_markdown(news_items: List[Dict], analysis_report: str) -> str:
    """
    生成Markdown。在新闻列表前插入分析报告。
    """
    md_content = f"# 基金新闻聚合 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
    configured_sources = list(set([s['name'].split('-')[0] for s in globals().get('sources', [])]))
    source_names = "、".join(configured_sources)
    md_content += f"来源：{source_names}（关键词：基金/实盘/观点/经验/推荐/策略）。总计 {len(news_items)} 条。\n"
    
    # 插入分析报告
    md_content += analysis_report
    
    # 插入原始新闻列表
    md_content += "\n---\n# 原始新闻列表\n\n"
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

def main():
    """主执行函数，协调抓取、分析、去重和文件生成。"""
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
                # 尝试解析为 datetime 对象
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        # 无法解析的排在最后
        return datetime(1900, 1, 1)

    unique_news.sort(key=sort_key, reverse=True)
    
    # 【核心】运行分析
    analysis_results = analyze_news(unique_news)
    analysis_report_md = generate_analysis_report(analysis_results, len(unique_news))
    
    # 生成MD
    md_content = generate_markdown(unique_news, analysis_report_md)
    output_file = 'fund_news.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。分析报告已生成并保存至 {output_file}")
    
    print("\n--- 分析报告摘要 ---")
    print(analysis_report_md.split('## 💰')[0])

if __name__ == "__main__":
    main()
