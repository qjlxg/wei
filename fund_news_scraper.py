import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import re
import xml.etree.ElementTree as ET
from dateutil import parser
import pytz
import matplotlib.pyplot as plt
from collections import Counter
import sqlite3
import json # 用于在 SQLite 中存储 List/Dict 字段

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
    # 新增规则以丰富内容
    r'科技股|AI算力|人形机器人': '科技创新/AI驱动产业链机会',
    r'消费|ETF|科技融合': '消费科技融合配置',
    r'公募规模|突破|增长': '公募行业规模扩张信号',
}

# 2. 经验教训 (行为/结果 -> 风险/教训)
LESSONS_MAP = {
    r'警惕|风险|教训|涉赌|跑输|内控': '【通用风险信号】识别到行业风险或负面经验教训',
    r'跑输大盘|未能满仓|红利板块': '新基金建仓策略与市场错配风险',
    r'基金经理|涉赌|免职': '基金经理道德风险与公司内控警示',
    r'机构大举增持|主动权益基金': '机构行为：主动权益基金仍是配置重点',
    # 新增规则
    r'伪成长|拥挤|陷阱': '成长赛道拥挤与伪成长风险',
    r'减持|高位': '股东减持与高位回调风险',
}

# 3. 行业趋势 (结构变化 -> 行业洞察)
TRENDS_MAP = {
    r'AI|投研|工业化|蚂蚁财富': '行业趋势：投研工业化和AI赋能',
    r'费率|下调|托管费|余额宝': '行业趋势：关注费率成本的长期下行',
    r'私募股权|子公司|广发基金': '行业趋势：头部公募的业务多元化',
    r'量化基金经理|主动基金|一拖多': '行业趋势：量化与主动投资边界模糊',
    # 新增规则
    r'REITs|获批|基础设施': 'REITs市场扩张与基础设施投资趋势',
    r'ESG|减排|绿色金融': 'ESG与绿色投资趋势',
    r'养老|第三支柱': '养老基金与长期投资体系建设',
}

# 聚合所有主题，用于长期趋势分析
ALL_TOPICS_MAP = {**CLUES_MAP, **LESSONS_MAP, **TRENDS_MAP}


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
    # 新增模板
    r'REITs|获批': '潜在影响：REITs获批将注入新活力，促进基础设施投资，吸引更多资金进入相关领域。',
    r'ESG|减排': '潜在影响：ESG政策强化将推动绿色转型，利好可持续投资主题基金。',
    r'养老|第三支柱': '潜在影响：养老体系完善将增加长期资金供给，稳定资本市场。',
    # 默认模板
    r'.*': '潜在影响：该新闻可能对相关板块产生中性影响，建议结合市场动态进一步评估。'
}

# 新增：简单情感分析关键词
POSITIVE_WORDS = ['看好', '上涨', '增长', '机会', '布局', '推荐']
NEGATIVE_WORDS = ['风险', '警惕', '跑输', '减持', '教训', '陷阱']

# -----------------------------------------------------------------


# --- 数据库管理类 ---
class DatabaseManager:
    def __init__(self, db_name='fund_news_analysis.db'):
        self.db_name = db_name
        self.conn = None
        self._connect()
        self._create_table()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row # 允许按列名访问
        
    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyzed_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE,
                pubDate TEXT,
                source TEXT,
                crawl_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sentiment TEXT,
                key_topics_json TEXT -- 存储主题列表的 JSON 字符串
            )
        ''')
        self.conn.commit()

    def get_existing_links(self) -> set:
        """从数据库获取所有已存在的链接，用于跨次运行去重。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT link FROM analyzed_news WHERE link IS NOT NULL AND link != 'N/A'")
        return {row['link'] for row in cursor.fetchall()}

    def store_news_and_analysis(self, news_item: Dict, analysis_result: Dict):
        """存储单条新闻及其分析结果。"""
        # 提取关键字段
        title = news_item['title']
        link = news_item.get('link', 'N/A')
        pubDate = news_item.get('pubDate', datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'))
        source = news_item['source']
        
        # 提取分析结果
        sentiment = analysis_result.get('sentiment', '中性 (Neutral)')
        key_topics_json = json.dumps(analysis_result.get('key_topics', []))
        
        cursor = self.conn.cursor()
        try:
            # 插入或替换，以处理无链接的重复标题
            cursor.execute('''
                INSERT INTO analyzed_news (title, link, pubDate, source, sentiment, key_topics_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, link, pubDate, source, sentiment, key_topics_json))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # 链接重复时，忽略该条目
            pass
        except Exception as e:
            print(f"Error storing news to DB: {e}")

    def get_topics_by_time_range(self, days: int) -> Dict[str, int]:
        """获取过去 N 天的主题计数。"""
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        
        # 仅使用 pubDate 字段进行时间过滤，因为它经过标准化处理
        cursor.execute("""
            SELECT key_topics_json
            FROM analyzed_news
            WHERE pubDate > ?
        """, (since_date,))
        
        topic_counter = Counter()
        for row in cursor.fetchall():
            try:
                topics = json.loads(row['key_topics_json'])
                topic_counter.update(topics)
            except (json.JSONDecodeError, TypeError):
                continue
        
        return dict(topic_counter)

    def close(self):
        if self.conn:
            self.conn.close()

# --- 辅助函数：时间解析和格式化 ---
def parse_and_format_time(pub_date: str) -> str:
    """解析时间字符串，转换为北京时间并格式化。"""
    if pub_date == 'N/A' or not pub_date:
        return 'N/A'
    try:
        # 尝试解析 pub_date，假定它可能是 UTC 或包含时区信息
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

# --- 新增：简单情感分析函数 ---
def simple_sentiment_analysis(text: str) -> str:
    """基于关键词的简单情感分析。"""
    pos_count = sum(1 for word in POSITIVE_WORDS if re.search(word, text, re.IGNORECASE))
    neg_count = sum(1 for word in NEGATIVE_WORDS if re.search(word, text, re.IGNORECASE))
    if pos_count > neg_count:
        return '正面 (Positive)'
    elif neg_count > pos_count:
        return '负面 (Negative)'
    else:
        return '中性 (Neutral)'

# --- 新增：详细新闻分析函数 ---
def detailed_analyze_news(item: Dict) -> Dict:
    """为单条新闻生成详细分析和潜在影响。"""
    text = item['title'] + ' ' + item['summary']
    analysis = {
        'title': item['title'],
        'detailed_summary': f"标题：{item['title']}\n摘要：{item['summary']}",
        'key_topics': [],
        'potential_impact': '',
        'sentiment': simple_sentiment_analysis(text)  
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
def fetch_rss_feed(url: str, source_name: str, limit: int = 20) -> List[Dict]:
    """获取并解析RSS feed，过滤包含'基金'、'实盘'、'观点'等关键词的条目。"""
    filtered_items = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        # 尝试直接请求
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            print(f"[{source_name}] Error parsing XML. Trying content decoding...")
            root = ET.fromstring(response.text.encode('utf-8'))

        items = root.findall('.//item') or root.findall('.//entry') # 兼容 RSS 和 Atom
        
        # 统一处理
        for item in items[:limit]:
            title_element = item.find('title')
            link_element = item.find('link')
            pub_date_element = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date') or item.find('published')
            summary_element = item.find('description') or item.find('summary') or item.find('content')

            title = title_element.text.strip() if title_element is not None and title_element.text else ''
            
            # 链接处理 (RSS <link> vs Atom <link href="...">)
            link = 'N/A'
            if link_element is not None:
                if link_element.text: # Standard RSS
                    link = link_element.text.strip()
                elif link_element.attrib.get('href'): # Atom/Other formats
                    link = link_element.attrib['href'].strip()

            pub_date_raw = pub_date_element.text.strip() if pub_date_element is not None and pub_date_element.text else 'N/A'
            summary_raw = summary_element.text.strip() if summary_element is not None and summary_element.text else ''
            
            summary = clean_html_summary(summary_raw, max_len=400)
            pub_date = parse_and_format_time(pub_date_raw)
            
            # 增加对更通用关键词（如股票、投资）的过滤
            if re.search(r'基金|实盘|观点|经验|推荐|策略|投资|股票|宏观|金融', title + summary, re.IGNORECASE):
                filtered_items.append({
                    'title': title,
                    'link': link,
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
            
            # Web 抓取的时间和摘要通常不准确，或需要深度解析，这里沿用 N/A
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
    新增：为所有新闻生成详细分析和潜在影响。
    """
    analysis = {
        'investment_clues': [],
        'experience_lessons': [],
        'industry_trends': [],
        'detailed_analyses': []  # 新增：所有新闻的详细分析
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

# --- 新增：长期趋势分析函数 ---
def generate_trend_analysis(db_manager: DatabaseManager) -> str:
    """对比过去 7 天和前 7 天的主题热度变化。"""
    
    # 获取近两周数据
    recent_topics = db_manager.get_topics_by_time_range(days=7) # P1: 近 7 天
    previous_topics = db_manager.get_topics_by_time_range(days=14) # P2: 近 14 天
    
    # 获取 P2 中的主题，然后减去 P1 中包含的主题，得到 P2-P1 (前 7 天)
    previous_period_topics = {
        topic: count for topic, count in previous_topics.items() 
        if topic not in recent_topics or count > recent_topics.get(topic, 0)
    }
    
    # 调整 P2-P1 计数
    p2_only_topics = {}
    for topic, total_count in previous_topics.items():
        recent_count = recent_topics.get(topic, 0)
        p2_only_topics[topic] = total_count - recent_count
    
    p1_topics = recent_topics
    p0_topics = {k: v for k, v in p2_only_topics.items() if v > 0} # 确保是前 7 天的独有计数
    
    # 统计所有出现过的主题
    all_topics = set(p1_topics.keys()) | set(p0_topics.keys())
    
    # 生成报告
    trend_report = "\n### 📈 主题热度变化 (近 7 天 vs 前 7 天)\n"
    trend_report += "对比显示了主要投资线索和行业趋势的关注度变化，变化率 $> 50\%$ 的主题将被高亮。\n\n"
    trend_report += "| 主题 | 近 7 天 (P1) | 前 7 天 (P0) | 变化率 | 趋势 |\n"
    trend_report += "| :--- | :---: | :---: | :---: | :---: |\n"
    
    sorted_topics = sorted(list(all_topics), key=lambda x: p1_topics.get(x, 0), reverse=True)
    
    for topic in sorted_topics:
        count_p1 = p1_topics.get(topic, 0)
        count_p0 = p0_topics.get(topic, 0)
        
        if count_p1 == 0 and count_p0 == 0:
            continue

        if count_p0 > 0:
            change_rate = (count_p1 - count_p0) / count_p0
            trend_icon = "⬆️" if change_rate > 0.1 else ("⬇️" if change_rate < -0.1 else "↔️")
            trend_str = f"{change_rate:.0%}"
        elif count_p1 > 0:
            # P0 为 0，P1 > 0，视为新热点
            change_rate = float('inf')
            trend_icon = "🔥"
            trend_str = "NEW"
        else:
            change_rate = 0
            trend_icon = "➖"
            trend_str = "0%"

        # 高亮显著变化
        if abs(change_rate) > 0.5 and change_rate != float('inf'):
             trend_str = f"**{trend_str}**"
        
        trend_report += f"| {topic} | {count_p1} | {count_p0} | {trend_str} | {trend_icon} |\n"

    if not all_topics:
        trend_report += "暂无足够历史数据进行长期趋势分析。\n"

    return trend_report


# --- 新增：生成统计图表 ---
def generate_stats_chart(analysis: Dict, output_file: str):
    """使用matplotlib生成简单条形图，展示类别计数。"""
    clue_count = len(analysis['investment_clues'])
    lesson_count = len(analysis['experience_lessons'])
    trend_count = len(analysis['industry_trends'])
    
    categories = ['Investment Clues', 'Experience Lessons', 'Industry Trends']
    counts = [clue_count, lesson_count, trend_count]
    
    plt.figure(figsize=(8, 5))
    plt.bar(categories, counts, color=['blue', 'orange', 'green'])
    plt.title('News Analysis Categories Count (Current Run)')
    plt.ylabel('Count')
    plt.savefig(f'{output_file}_stats.png')
    plt.close()
    print(f"Generated stats chart: {output_file}_stats.png")

# --- 生成分析报告 ---
def generate_analysis_report(analysis: Dict, total_count: int, trend_report: str) -> str:
    """根据分析结果生成结构化 Markdown 报告。新增详细分析部分、统计概述和趋势分析。"""
    md_report = "\n---\n"
    md_report += "# 📰 基金投资策略分析报告\n\n"
    md_report += f"本报告根据从 {total_count} 条新闻中提取的高价值信息生成，旨在为您提供 **买入指引、风险规避和行业洞察**。\n\n"

    # 新增：统计概述
    md_report += "## 📊 统计概述\n"
    md_report += f"- 本次抓取投资线索数量: {len(analysis['investment_clues'])}\n"
    md_report += f"- 本次抓取经验教训数量: {len(analysis['experience_lessons'])}\n"
    md_report += f"- 本次抓取行业趋势数量: {len(analysis['industry_trends'])}\n"
    md_report += f"- 总新闻条目: {total_count}\n\n"
    
    # 引入长期趋势分析
    md_report += "## 长期趋势分析\n"
    md_report += trend_report

    # 1. 投资线索
    md_report += "\n## 💰 投资线索与市场焦点 (买入指引)\n"
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
        md_report += "| 新闻标题 | 关键主题 | 情感分析 | 潜在影响 |\n"
        md_report += "| :--- | :--- | :--- | :--- |\n"
        
        for det in analysis['detailed_analyses']:
            topics_str = '; '.join(det['key_topics']) if det['key_topics'] else '无特定主题'
            md_report += f"| {det['title']} | {topics_str} | {det['sentiment']} | **{det['potential_impact']}** |\n"
    else:
        md_report += "暂无详细分析。\n"

    return md_report


# --- 数据源配置外部化 (使用上一个版本的扩展配置) ---
proxy_base = 'https://rsshub.rss.zgdnz.cc'
sources = [
    # --- 原有 RSS Hub 代理源 ---
    {'url': f'{proxy_base}/cls/telegraph/fund', 'name': '财联社-基金电报', 'type': 'rss'},
    {'url': f'{proxy_base}/eastmoney/report/strategyreport', 'name': '东方财富-策略报告', 'type': 'rss'},
    {'url': f'{proxy_base}/gelonghui/home/fund', 'name': '格隆汇-基金', 'type': 'rss'},
    {'url': f'{proxy_base}/stcn/article/list/fund', 'name': '证券时报-基金列表', 'type': 'rss'},
    {'url': f'{proxy_base}/21caijing/channel/%E8%AF%81%E5%88%B8/%E8%B5%A2%E5%9F%BA%E9%87%91', 'name': '21财经-赢基金', 'type': 'rss'},
    {'url': f'{proxy_base}/xueqiu/fund', 'name': '雪球-基金RSS', 'type': 'rss'},  
    {'url': f'{proxy_base}/zhihu/topic/19550517', 'name': '知乎-基金话题', 'type': 'rss'}, 
    {'url': f'{proxy_base}/sina/finance/fund', 'name': '新浪财经-基金 (代理)', 'type': 'rss'},  
    
    # --- 原有 Web 抓取源 ---
    {
        'url': 'https://xueqiu.com/k?q=%E5%9F%BA%E9%87%91',
        'name': '雪球-基金搜索 (Web)',
        'type': 'web',
        'selector': '.search__list .search-result-item .search-title a' 
    },
    {'url': 'https://blog.csdn.net/category_10134701.html?spm=1001.2101.3001.5700', 'name': 'CSDN-基金博客 (Web)', 'type': 'web', 'selector': '.blog-list-box .title a'}, 

    # --- 新增直接 RSS 源 ---
    {'url': 'http://rss.eastmoney.com/rss_partener.xml', 'name': '东方财富-合作伙伴 (RSS)', 'type': 'rss'},
    {'url': 'http://rss.sina.com.cn/finance/fund.xml', 'name': '新浪财经-基金要闻 (RSS)', 'type': 'rss'},
    {'url': 'http://rss.sina.com.cn/roll/finance/hot_roll.xml', 'name': '新浪财经-要闻汇总 (RSS)', 'type': 'rss'},
    {'url': 'https://dedicated.wallstreetcn.com/rss.xml', 'name': '华尔街见闻 (RSS)', 'type': 'rss'},
    {'url': 'https://36kr.com/feed', 'name': '36氪 (RSS)', 'type': 'rss'},
    {'url': 'https://www.hket.com/rss/china', 'name': '香港經濟日報 (RSS)', 'type': 'rss'}, 
    {'url': 'http://news.baidu.com/n?cmd=1&class=stock&tn=rss&sub=0', 'name': '百度-股票焦点 (RSS)', 'type': 'rss'},
    {'url': 'https://www.chinanews.com.cn/rss/finance.xml', 'name': '中新网财经 (RSS)', 'type': 'rss'},
    {'url': 'https://www.marketwatch.com/rss/topstories', 'name': 'MarketWatch-国际要闻 (RSS)', 'type': 'rss'},
    {'url': 'https://www.stats.gov.cn/sj/zxfb/rss.xml', 'name': '国家统计局-最新发布 (RSS)', 'type': 'rss'}, 
]

def generate_markdown(news_items: List[Dict], analysis_report: str, timestamp_str: str) -> str:
    """
    生成Markdown。在新闻列表前插入分析报告。
    """
    md_content = f"# 基金新闻聚合 ({timestamp_str})\n\n"
    # 调整源名称提取，避免冗余信息
    configured_sources = list(set([s['name'].split('(')[0].strip() for s in globals().get('sources', [])]))
    source_names = "、".join(configured_sources)
    md_content += f"来源：{source_names}（关键词：基金/实盘/观点/经验/推荐/策略/投资/宏观/金融）。总计 {len(news_items)} 条。\n"
    
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
    
    # 初始化数据库管理器
    db_manager = DatabaseManager()
    
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    date_str = now.strftime('%Y%m%d') 
    output_file = f'fund_news_{date_str}.md'
    
    all_news = []
    print(f"[{timestamp_str}] 开始抓取基金新闻 (已扩展来源和通用关键词)...")
    
    # 1. 获取已存在的链接，用于跨次去重
    existing_links = db_manager.get_existing_links()
    
    for source in sources:
        print(f"处理来源: {source['name']}")
        if source['type'] == 'rss':
            items = fetch_rss_feed(source['url'], source['name'], limit=20) 
        else:
            items = fetch_web_page(source['url'], source['name'], source.get('selector'), limit=15)
        
        # 针对当前批次进行去重
        current_batch_unique = []
        batch_seen = set()
        for item in items:
            link = item.get('link', 'N/A')
            # 跨次去重
            if link and link != 'N/A' and link in existing_links:
                continue
            # 批次内去重
            if (item['title'], item['source']) not in batch_seen:
                current_batch_unique.append(item)
                batch_seen.add((item['title'], item['source']))
                if link and link != 'N/A':
                    existing_links.add(link) # 提前加入，避免本批次内重复

        all_news.extend(current_batch_unique)

    # 2. 排序：按时间倒序排列
    def sort_key(item):
        time_str = item['pubDate']
        if time_str and time_str != 'N/A':
            try:
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return datetime(1900, 1, 1)

    unique_news = all_news # all_news 已经包含了批次去重和跨次去重的逻辑
    unique_news.sort(key=sort_key, reverse=True)
    
    # 3. 运行分析和存储
    analysis_results = analyze_news(unique_news)
    
    # 将新的新闻及其分析结果存入数据库
    for item, detailed_analysis in zip(unique_news, analysis_results['detailed_analyses']):
        # item: 原始新闻数据
        # detailed_analysis: 包含 sentiment 和 key_topics 的分析结果
        db_manager.store_news_and_analysis(item, detailed_analysis)
    
    # 4. 生成长期趋势分析
    trend_report_md = generate_trend_analysis(db_manager)
    
    # 5. 生成报告
    analysis_report_md = generate_analysis_report(analysis_results, len(unique_news), trend_report_md)
    
    # 生成统计图表
    generate_stats_chart(analysis_results, date_str)
    
    # 生成MD
    md_content = generate_markdown(unique_news, analysis_report_md, timestamp_str)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"收集到 {len(unique_news)} 条独特基金新闻。分析报告已生成并保存至 {output_file}")
    
    print("\n--- 分析报告摘要 ---")
    print(analysis_report_md.split('## 💰')[0])

    # 关闭数据库连接
    db_manager.close()

if __name__ == "__main__":
    main()
