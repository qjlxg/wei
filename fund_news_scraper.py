import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET
from dateutil import parser
import pytz

# --- 【核心配置】分析规则库：通用、可扩展的分析逻辑 ---

# 1. 投资线索 (标的/策略 -> 总结)
CLUES_MAP = {
    # 策略通用词：识别任何表达明确买入/看好/配置意图的文章 (强化通用词，抓住行为)
    r'看好|建议配置|策略主线|聚焦|布局|推荐|金股|实盘': '【通用策略信号】识别到明确的配置建议或策略主线',
    
    # 宏观策略与周期
    r'宏观|策略报告|周期|四中全会|十五五': '【宏观策略信号】宏观或周期性主题报告',
    
    # 特指信号：保留高价值人物/机构的关键词，但其定位是“信号”，而非特定人
    r'李蓓|半夏|中证500|IC': '私募观点：中证500/科技成长策略',
    r'华安证券|成长产业|AI|军工': '券商观点：AI/军工/新成长产业链配置',
    r'开源证券|金股策略|科技|港股': '券商观点：AI+自主可控科技主线',
    r'ETF|股票ETF|百亿俱乐部|吸金': '资金流向/股票ETF/吸金赛道',
    r'贵金属|黄金|避险': '资产对冲/避险配置 (贵金属)',
    r'均衡配置|光伏|化工|农业|有色|银行': '低位/均衡板块配置建议',
}

# 2. 经验教训 (行为/结果 -> 风险/教训)
LESSONS_MAP = {
    r'警惕|风险|教训|涉赌|跑输|内控': '【通用风险信号】识别到行业风险或负面经验教训',
    r'跑输大盘|未能满仓|红利板块': '新基金建仓策略与市场错配风险',
    r'基金经理|涉赌|免职': '基金经理道德风险与公司内控警示',
    r'机构大举增持|主动权益基金': '机构行为：主动权益基金仍是配置重点',
}

# 3. 行业趋势 (结构变化 -> 行业洞察)
TRENDS_MAP = {
    r'AI|投研|工业化|蚂蚁财富': '行业趋势：投研工业化和AI赋能',
    r'费率|下调|托管费|余额宝': '行业趋势：关注费率成本的长期下行',
    r'私募股权|子公司|广发基金': '行业趋势：头部公募的业务多元化',
    r'量化基金经理|主动基金|一拖多': '行业趋势：量化与主动投资边界模糊',
}

# 新增：潜在影响模板库 (基于关键词生成新闻影响总结)
IMPACT_TEMPLATES = {
    r'AI|算力|科技龙头|产业链': '潜在影响：可能推动科技板块短期上涨，但需警惕估值泡沫风险，建议关注产业链中低估值标的。',
    r'费率|降费|货币基金': '潜在影响：降低投资者成本，提升基金吸引力，长期利好公募行业规模扩张，但短期可能挤压基金公司利润。',
    r'风险|警惕|跑输|道德风险': '潜在影响：增加市场波动性，投资者应加强风险管理，避免追高热门赛道。',
    r'ETF|吸金|资金流向': '潜在影响：加速资金向热门主题倾斜，增强市场流动性，但可能放大板块轮动效应。',
    r'宏观|策略报告|震荡上行': '潜在影响：四季度市场或呈N型走势，科技与反内卷板块受益，建议均衡配置。',
    r'私募观点|中证500': '潜在影响：中证500指数可能吸引更多资金流入科技成长股，提升指数表现。',
    r'贵金属|避险': '潜在影响：在地缘风险下，贵金属作为对冲工具需求上升，配置价值提升。',
    r'业务多元化|子公司': '潜在影响：公募扩展私募股权等领域，增强综合竞争力，利好长期投资者。',
    # 默认模板
    r'.*': '潜在影响：该新闻可能对相关板块产生中性影响，建议结合市场动态进一步评估。'
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

# --- 新增：详细新闻分析函数 ---
def detailed_analyze_news(item: Dict) -> Dict:
    """为单条新闻生成详细分析和潜在影响。"""
    text = item['title'] + ' ' + item['summary']
    analysis = {
        'title': item['title'],
        'detailed_summary': f"标题：{item['title']}\n摘要：{item['summary']}",
        'key_topics': [],
        'potential_impact': ''
    }
    
    # 提取关键主题（基于现有MAP扩展）
    for map_dict in [CLUES_MAP, LESSONS_MAP, TRENDS_MAP]:
        for pattern, desc in map_dict.items():
            if re.search(pattern, text, re.IGNORECASE):
                analysis['key_topics'].append(desc)
    
    # 生成潜在影响
    impact_found = False
    for pattern, impact in IMPACT_TEMPLATES.items():
        if re.search(pattern, text, re.IGNORECASE):
            analysis['potential_impact'] = impact
            impact_found = True
            break
    if not impact_found:
        analysis['potential_impact'] = IMPACT_TEMPLATES['.*']
    
    return analysis

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


# --- 【核心】新闻分析函数：基于规则匹配（侧重通用性） ---
def analyze_news(news_items: List[Dict]) -> Dict:
    """
    基于关键词和规则库，从新闻列表中提取投资线索和经验教训。
    逻辑简化为：只要匹配到任意一个通用或特定的规则，就提炼该信号。
    新增：为所有新闻生成详细分析和潜在影响。
    """
    analysis = {
        'investment_clues': [],
        'experience_lessons': [],
        'industry_trends': [],
        'detailed_analyses': []  # 新增：所有新闻的详细分析
    }

    seen_clues = set()
    seen_lessons = set()
    seen_trends = set()

    for item in news_items:
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
        
        # 新增：为所有新闻生成详细分析
        detailed = detailed_analyze_news(item)
        analysis['detailed_analyses'].append(detailed)
                
    return analysis

# --- 生成分析报告 ---
def generate_analysis_report(analysis: Dict, total_count: int) -> str:
    """根据分析结果生成结构化 Markdown 报告。新增详细分析部分。"""
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

    # 新增：详细新闻分析与潜在影响
    md_report += "\n## 🔍 所有新闻详细分析与潜在影响\n"
    if analysis['detailed_analyses']:
        md_report += "| 新闻标题 | 关键主题 | 潜在影响 |\n"
        md_report += "| :--- | :--- | :--- |\n"
        
        for det in analysis['detailed_analyses']:
            topics_str = '; '.join(det['key_topics']) if det['key_topics'] else '无特定主题'
            md_report += f"| {det['title']} | {topics_str} | **{det['potential_impact']}** |\n"
    else:
        md_report += "暂无详细分析。\n"

    return md_report


# --- 数据源配置外部化 (保持不变，并扩展新来源) ---
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
    },
    # 新增扩展来源：社区和个人博客（基于可用测试）
    {'url': f'{proxy_base}/xueqiu/fund', 'name': '雪球-基金RSS', 'type': 'rss'},  # 雪球基金社区RSS
    {'url': f'{proxy_base}/zhihu/topic/19550517', 'name': '知乎-基金话题', 'type': 'rss'},  # 知乎基金专栏社区
    {'url': 'https://dbarobin.com/rss.xml', 'name': '区块链罗宾-投资博客', 'type': 'rss'}  # 个人投资博客（区块链/基金相关）
]

def generate_markdown(news_items: List[Dict], analysis_report: str, timestamp_str: str) -> str:
    """
    生成Markdown。在新闻列表前插入分析报告。
    """
    md_content = f"# 基金新闻聚合 ({timestamp_str})\n\n"
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
    
    # --- 关键修改 1: 获取带日期时间戳的文件名 ---
    # 使用当前北京时间作为时间戳，用于命名和报告标题
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    # 文件名使用 YYYYMMDD 格式，避免覆盖
    date_str = now.strftime('%Y%m%d') 
    output_file = f'fund_news_{date_str}.md'
    # --------------------------------------------------
    
    all_news = []
    print(f"[{timestamp_str}] 开始抓取基金新闻 (已扩展关键词和深度)...")
    
    for source in sources:
        print(f"处理来源: {source['name']} ({source['url']})")
        if source['type'] == 'rss':
            items = fetch_rss_feed(source['url'], source['name'], limit=15)
        else:
            # 这里的 source_name 变量需要从 source 字典中获取
            items = fetch_web_page(source['url'], source['name'], source.get('selector'), limit=15)
        all_news.extend(items)
    
    # 去重
    unique_news = []
    seen_links = set()
    for news in all_news:
        if news['link'] and news['link'] != 'N/A' and news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
        # 如果链接不可用，则根据标题和来源进行去重
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
    
    # 【核心】运行分析
    analysis_results = analyze_news(unique_news)
    analysis_report_md = generate_analysis_report(analysis_results, len(unique_news))
    
    # 生成MD
    # 关键修改 2: 传入 timestamp_str 到 generate_markdown
    md_content = generate_markdown(unique_news, analysis_report_md, timestamp_str)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。分析报告已生成并保存至 {output_file}")
    
    print("\n--- 分析报告摘要 ---")
    print(analysis_report_md.split('## 💰')[0])

if __name__ == "__main__":
    main()
