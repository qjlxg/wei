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
import json
import logging
import time
from wordcloud import WordCloud
import jieba
from retry import retry
# 增加 os 和 json 模块用于配置分离
import os 
import json 

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('fund_news_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 【核心配置】分析规则库：通用、可扩展的分析逻辑 ---

# 1. 投资线索 (标的/策略 -> 总结)
CLUES_MAP = {
    r'看好|建议配置|策略主线|聚焦|布局|推荐|金股|实盘': {'desc': '【通用策略信号】识别到明确的配置建议或策略主线', 'weight': 1.0},
    r'宏观|策略报告|周期|四中全会|十五五': {'desc': '【宏观策略信号】宏观或周期性主题报告', 'weight': 0.8},
    r'李蓓|半夏|中证500|IC': {'desc': '私募观点：中证500/科技成长策略', 'weight': 0.9},
    r'华安证券|成长产业|AI|军工': {'desc': '券商观点：AI/军工/新成长产业链配置', 'weight': 0.9},
    r'开源证券|金股策略|科技|港股': {'desc': '券商观点：AI+自主可控科技主线', 'weight': 0.9},
    r'ETF|股票ETF|百亿俱乐部|吸金': {'desc': '资金流向/股票ETF/吸金赛道', 'weight': 0.8},
    r'贵金属|黄金|避险': {'desc': '资产对冲/避险配置 (贵金属)', 'weight': 0.7},
    r'均衡配置|光伏|化工|农业|有色|银行': {'desc': '低位/均衡板块配置建议', 'weight': 0.7},
    r'科技股|AI算力|人形机器人': {'desc': '科技创新/AI驱动产业链机会', 'weight': 1.0},
    r'消费|ETF|科技融合': {'desc': '消费科技融合配置', 'weight': 0.8},
    r'公募规模|突破|增长': {'desc': '公募行业规模扩张信号', 'weight': 0.7},
    # 新增规则：加强新能源和海外市场分析
    r'新能源|电池|光伏|风电': {'desc': '新能源配置机会', 'weight': 0.8},
    r'海外|港股|美股|QDII': {'desc': '海外资产配置信号', 'weight': 0.7},
}

# 2. 经验教训 (行为/结果 -> 风险/教训)
LESSONS_MAP = {
    r'警惕|风险|教训|涉赌|跑输|内控': {'desc': '【通用风险信号】识别到行业风险或负面经验教训', 'weight': 1.0},
    r'跑输大盘|未能满仓|红利板块': {'desc': '新基金建仓策略与市场错配风险', 'weight': 0.9},
    r'基金经理|涉赌|免职': {'desc': '基金经理道德风险与公司内控警示', 'weight': 1.0},
    r'机构大举增持|主动权益基金': {'desc': '机构行为：主动权益基金仍是配置重点', 'weight': 0.8},
    r'伪成长|拥挤|陷阱': {'desc': '成长赛道拥挤与伪成长风险', 'weight': 0.9},
    r'减持|高位': {'desc': '股东减持与高位回调风险', 'weight': 0.9},
    # 新增规则：加强市场波动和政策风险
    r'波动|回调|泡沫': {'desc': '市场波动与估值回调风险', 'weight': 0.9},
    r'政策|监管|合规': {'desc': '政策变动与监管合规风险', 'weight': 0.8},
}

# 3. 行业趋势 (结构变化 -> 行业洞察)
TRENDS_MAP = {
    r'AI|投研|工业化|蚂蚁财富': {'desc': '行业趋势：投研工业化和AI赋能', 'weight': 0.9},
    r'费率|下调|托管费|余额宝': {'desc': '行业趋势：关注费率成本的长期下行', 'weight': 0.8},
    r'私募股权|子公司|广发基金': {'desc': '行业趋势：头部公募的业务多元化', 'weight': 0.8},
    r'量化基金经理|主动基金|一拖多': {'desc': '行业趋势：量化与主动投资边界模糊', 'weight': 0.8},
    r'REITs|获批|基础设施': {'desc': 'REITs市场扩张与基础设施投资趋势', 'weight': 0.7},
    r'ESG|减排|绿色金融': {'desc': 'ESG与绿色投资趋势', 'weight': 0.7},
    r'养老|第三支柱': {'desc': '养老基金与长期投资体系建设', 'weight': 0.7},
    # 新增规则：加强数字化和跨境趋势
    r'数字化|FinTech|区块链': {'desc': '数字化转型与FinTech趋势', 'weight': 0.8},
    r'跨境|REITs|海外基金': {'desc': '跨境投资与REITs国际化趋势', 'weight': 0.7},
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
    r'REITs|获批': '潜在影响：REITs获批将注入新活力，促进基础设施投资，吸引更多资金进入相关领域。',
    r'ESG|减排': '潜在影响：ESG政策强化将推动绿色转型，利好可持续投资主题基金。',
    r'养老|第三支柱': '潜在影响：养老体系完善将增加长期资金供给，稳定资本市场。',
    # 新增模板：加强新能源和海外影响
    r'新能源|电池|光伏|风电': '潜在影响：政策支持下新能源板块或持续反弹，建议配置龙头企业，但关注供应链风险。',
    r'海外|港股|美股|QDII': '潜在影响：全球流动性宽松利好海外资产，QDII基金配置价值提升，但需警惕汇率波动。',
    r'波动|回调|泡沫': '潜在影响：短期市场调整可能加剧，投资者应分散持仓，等待低位布局机会。',
    r'政策|监管|合规': '潜在影响：新政落地或重塑行业格局，利好合规头部机构，但中小玩家面临整合压力。',
    r'数字化|FinTech|区块链': '潜在影响：FinTech创新加速金融效率提升，相关基金或迎来增长周期。',
    r'跨境|REITs': '潜在影响：跨境REITs扩张将多元化投资渠道，吸引海外资金流入基础设施领域。',
    r'.*': '潜在影响：该新闻可能对相关板块产生中性影响，建议结合市场动态进一步评估。'
}

# 新增：简单情感分析关键词
POSITIVE_WORDS = ['看好', '上涨', '增长', '机会', '布局', '推荐', '潜力', '突破']
NEGATIVE_WORDS = ['风险', '警惕', '跑输', '减持', '教训', '陷阱', '波动', '下跌']

# --- 新增：动态关键词扩展 ---
def extract_dynamic_keywords(text: str, min_freq: int = 2) -> List[str]:
    """基于 jieba 分词动态提取高频关键词，排除已有规则中的关键词。"""
    # 移除标点符号和数字，只保留中文、英文、空格
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z\s]', '', text)
    words = jieba.cut(clean_text)
    word_freq = Counter(words)
    
    # 排除通用停用词和规则中的词
    stopwords = {'的', '了', '是', '在', '和', '也', '等', '基金', '投资', '分析', '报告', '金融', '证券', '公司', '公布', '数据'}
    existing_keywords = set()
    for pattern in ALL_TOPICS_MAP.keys():
        existing_keywords.update(pattern.split('|'))
    
    dynamic_keywords = [
        word for word, freq in word_freq.items() 
        if freq >= min_freq and 
           word not in existing_keywords and 
           word not in stopwords and
           len(word) > 1
    ]
    return dynamic_keywords[:5] # 返回前5个高频词

# --- 数据库管理类 ---
class DatabaseManager:
    def __init__(self, db_name='fund_news_analysis.db'):
        self.db_name = db_name
        self.conn = None
        self._connect()
        self._create_table()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        # 优化：启用 WAL 模式，提升并发性能
        self.conn.execute('PRAGMA journal_mode=WAL')
        
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
                key_topics_json TEXT,
                dynamic_keywords_json TEXT
            )
        ''')
        # 优化：为常用查询字段添加索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pubDate ON analyzed_news(pubDate)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON analyzed_news(source)')
        self.conn.commit()

    def get_existing_links(self) -> set:
        cursor = self.conn.cursor()
        cursor.execute("SELECT link FROM analyzed_news WHERE link IS NOT NULL AND link != 'N/A'")
        return {row['link'] for row in cursor.fetchall()}

    def store_news_and_analysis(self, news_item: Dict, analysis_result: Dict):
        title = news_item['title']
        link = news_item.get('link', 'N/A')
        pubDate = news_item.get('pubDate', datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'))
        source = news_item['source']
        sentiment = analysis_result.get('sentiment', '中性 (Neutral)')
        key_topics_json = json.dumps(analysis_result.get('key_topics', []))
        dynamic_keywords_json = json.dumps(analysis_result.get('dynamic_keywords', []))
        
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO analyzed_news (title, link, pubDate, source, sentiment, key_topics_json, dynamic_keywords_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (title, link, pubDate, source, sentiment, key_topics_json, dynamic_keywords_json))
            self.conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate link found, skipping: {link}")
        except Exception as e:
            logger.error(f"Error storing news to DB: {e}")

    def get_topics_by_time_range(self, days: int) -> Dict[str, int]:
        since_date = (datetime.now(pytz.timezone('Asia/Shanghai')) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute("SELECT key_topics_json FROM analyzed_news WHERE pubDate > ?", (since_date,))
        
        topic_counter = Counter()
        for row in cursor.fetchall():
            try:
                topics = json.loads(row['key_topics_json'])
                topic_counter.update(topics)
            except (json.JSONDecodeError, TypeError):
                continue
        return dict(topic_counter)

    def get_dynamic_keywords_by_time_range(self, days: int) -> Dict[str, int]:
        since_date = (datetime.now(pytz.timezone('Asia/Shanghai')) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute("SELECT dynamic_keywords_json FROM analyzed_news WHERE pubDate > ?", (since_date,))
        
        keyword_counter = Counter()
        for row in cursor.fetchall():
            try:
                keywords = json.loads(row['dynamic_keywords_json'])
                keyword_counter.update(keywords)
            except (json.JSONDecodeError, TypeError):
                continue
        return dict(keyword_counter)

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

# --- 辅助函数：时间解析和格式化 ---
def parse_and_format_time(pub_date: str) -> str:
    if pub_date == 'N/A' or not pub_date:
        return 'N/A'
    try:
        dt_utc = parser.parse(pub_date).replace(tzinfo=pytz.utc)
        dt_local = dt_utc.astimezone(pytz.timezone('Asia/Shanghai'))
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        logger.warning(f"Failed to parse date: {pub_date}")
        return pub_date

# --- 辅助函数：HTML清理和摘要处理 ---
def clean_html_summary(summary: str, max_len: int = 400) -> str:
    if not summary:
        return '无摘要'
    clean_soup = BeautifulSoup(summary, 'html.parser')
    clean_text = clean_soup.get_text(strip=True)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if len(clean_text) > max_len:
        return clean_text[:max_len] + '...'
    return clean_text

# --- 新增：优化情感分析 ---
def weighted_sentiment_analysis(text: str) -> tuple[str, float]:
    pos_score = 0
    neg_score = 0
    for word in POSITIVE_WORDS:
        if re.search(word, text, re.IGNORECASE):
            pos_score += text.lower().count(word.lower()) * 1.0
    for word in NEGATIVE_WORDS:
        if re.search(word, text, re.IGNORECASE):
            neg_score += text.lower().count(word.lower()) * 1.0
    
    total_score = pos_score - neg_score
    if total_score > 0:
        sentiment = '正面 (Positive)'
    elif total_score < 0:
        sentiment = '负面 (Negative)'
    else:
        sentiment = '中性 (Neutral)'
    return sentiment, total_score

# --- 详细新闻分析函数 ---
def detailed_analyze_news(item: Dict) -> Dict:
    text = item['title'] + ' ' + item['summary']
    analysis = {
        'title': item['title'],
        'detailed_summary': f"标题：{item['title']}\n摘要：{item['summary']}",
        'key_topics': [],
        'potential_impact': '',
        'sentiment': '中性 (Neutral)',
        'sentiment_score': 0.0,
        'dynamic_keywords': extract_dynamic_keywords(text)
    }
    
    # 提取关键主题（考虑权重）
    for map_dict in [CLUES_MAP, LESSONS_MAP, TRENDS_MAP]:
        for pattern, info in map_dict.items():
            if re.search(pattern, text, re.IGNORECASE):
                analysis['key_topics'].append(info['desc'])
    
    # 生成潜在影响
    impact_found = False
    for pattern, impact in IMPACT_TEMPLATES.items():
        if re.search(pattern, text, re.IGNORECASE):
            analysis['potential_impact'] = impact
            impact_found = True
            break
    if not impact_found:
        analysis['potential_impact'] = IMPACT_TEMPLATES['.*']
    
    # 优化情感分析
    analysis['sentiment'], analysis['sentiment_score'] = weighted_sentiment_analysis(text)
    
    return analysis

# --- 核心抓取函数：RSS ---
@retry(tries=3, delay=2, backoff=2, logger=logger)
def fetch_rss_feed(url: str, source_name: str, limit: int = 20) -> List[Dict]:
    filtered_items = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(url, timeout=10, headers=headers)
    response.raise_for_status()
    
    try:
        # 尝试直接解析
        root = ET.fromstring(response.content)
    except ET.ParseError:
        logger.warning(f"[{source_name}] Error parsing XML. Trying content decoding...")
        # 尝试用 utf-8 解码后解析，以处理编码问题
        root = ET.fromstring(response.text.encode('utf-8'))

    items = root.findall('.//item') or root.findall('.//entry')
    for item in items[:limit]:
        # 修复：使用显式的 'is not None' 检查
        title_element = item.find('title')
        link_element = item.find('link')
        pub_date_element = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date') or item.find('published')
        summary_element = item.find('description') or item.find('summary') or item.find('content')

        title = title_element.text.strip() if title_element is not None and title_element.text else ''
        
        link = 'N/A'
        if link_element is not None:
            if link_element.text:
                link = link_element.text.strip()
            elif link_element.attrib.get('href'):
                link = link_element.attrib['href'].strip()

        pub_date_raw = pub_date_element.text.strip() if pub_date_element is not None and pub_date_element.text else 'N/A'
        summary_raw = summary_element.text.strip() if summary_element is not None and summary_element.text else ''
        
        summary = clean_html_summary(summary_raw, max_len=400)
        pub_date = parse_and_format_time(pub_date_raw)
        
        if re.search(r'基金|实盘|观点|经验|推荐|策略|投资|股票|宏观|金融', title + summary, re.IGNORECASE):
            filtered_items.append({
                'title': title,
                'link': link,
                'pubDate': pub_date,
                'summary': summary,
                'source': source_name
            })
    return filtered_items

# --- 核心抓取函数：Web ---
@retry(tries=3, delay=2, backoff=2, logger=logger)
def fetch_web_page(url: str, source_name: str, selector: str, limit: int = 15) -> List[Dict]:
    filtered_items = []
    
    # 提取基础域名用于构建 Referer
    base_domain = url.split('/')[2]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/555.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/555.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': f'https://{base_domain}/' 
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
        
        # 修复链接拼接：确保 Web 链接是完整的
        if link and not link.startswith('http'):
            # 兼容需要完整链接的情况
            link = requests.compat.urljoin(url, link)
        
        # 优化：尝试从父级或直接兄弟节点寻找摘要，提高 Web 抓取的通用性
        parent = item.find_parent() if item.find_parent() else soup
        summary_tag = parent.select_one('.summary, .search-summary, .search-snippet, .search-content, .content, p')
        summary_raw = summary_tag.get_text(strip=True) if summary_tag else title
        summary = clean_html_summary(summary_raw, max_len=400)
        
        if re.search(r'基金|实盘|观点|经验|推荐|策略|投资|股票|宏观|金融', title + summary, re.IGNORECASE):
            filtered_items.append({
                'title': title,
                'link': link if link else 'N/A',
                'pubDate': 'N/A',
                'summary': summary,
                'source': source_name
            })
    return filtered_items

# --- 核心新闻分析函数 ---
def analyze_news(news_items: List[Dict]) -> Dict:
    analysis = {
        'investment_clues': [],
        'experience_lessons': [],
        'industry_trends': [],
        'detailed_analyses': []
    }
    seen_clues = set()
    seen_lessons = set()
    seen_trends = set()

    for item in news_items:
        text = item['title'] + ' ' + item['summary']
        
        # 1. 投资线索
        for pattern, info in CLUES_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and info['desc'] not in seen_clues:
                analysis['investment_clues'].append({
                    'focus': info['desc'],
                    'title': item['title'],
                    'link': item['link'],
                    'weight': info['weight']
                })
                seen_clues.add(info['desc'])
        
        # 2. 经验教训
        for pattern, info in LESSONS_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and info['desc'] not in seen_lessons:
                analysis['experience_lessons'].append({
                    'lesson': info['desc'],
                    'title': item['title'],
                    'link': item['link'],
                    'weight': info['weight']
                })
                seen_lessons.add(info['desc'])
        
        # 3. 行业趋势
        for pattern, info in TRENDS_MAP.items():
            if re.search(pattern, text, re.IGNORECASE) and info['desc'] not in seen_trends:
                analysis['industry_trends'].append({
                    'trend': info['desc'],
                    'title': item['title'],
                    'link': item['link'],
                    'weight': info['weight']
                })
                seen_trends.add(info['desc'])
        
        detailed = detailed_analyze_news(item)
        analysis['detailed_analyses'].append(detailed)
        
    # 按权重排序
    analysis['investment_clues'].sort(key=lambda x: x['weight'], reverse=True)
    analysis['experience_lessons'].sort(key=lambda x: x['weight'], reverse=True)
    analysis['industry_trends'].sort(key=lambda x: x['weight'], reverse=True)
    
    return analysis

# --- 词云字体路径查找辅助函数 ---
def get_chinese_font_path() -> str | None:
    """尝试查找常见的系统/默认中文字体路径"""
    # 常见 Windows 路径
    if os.name == 'nt' and os.path.exists('C:/Windows/Fonts/simhei.ttf'):
        return 'C:/Windows/Fonts/simhei.ttf'
    
    # 常见 Linux/macOS/CI 路径
    for path in [
        'SimHei.ttf', # 脚本同目录
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    ]:
        if os.path.exists(path):
            return path
            
    return None

# --- 新增：生成词云 (已修复 OSEerror) ---
def generate_wordcloud(keywords: Dict[str, int], output_file: str):
    if not keywords:
        logger.info("No keywords for wordcloud generation.")
        return
    
    font_path = get_chinese_font_path()
    
    if font_path is None:
        logger.error("WordCloud generation failed (OSError: cannot open resource): No valid Chinese font found. Skipping wordcloud generation. Please install SimHei.ttf or a CJK font in the execution environment.")
        return # 修复：找不到字体时直接返回，避免 OSError

    try:
        wordcloud = WordCloud(
            font_path=font_path,
            width=800, height=400, background_color='white', max_words=50
        ).generate_from_frequencies(keywords)
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.savefig(f'{output_file}_wordcloud.png')
        plt.close()
        logger.info(f"Generated wordcloud: {output_file}_wordcloud.png")
    except Exception as e:
        logger.error(f"WordCloud generation failed unexpectedly: {e}")

# --- 长期趋势分析函数 ---
def generate_trend_analysis(db_manager: DatabaseManager) -> str:
    recent_topics = db_manager.get_topics_by_time_range(days=7)
    previous_topics = db_manager.get_topics_by_time_range(days=14)
    recent_keywords = db_manager.get_dynamic_keywords_by_time_range(days=7)
    
    # 计算前 7 天的独有计数 (P0)
    p2_only_topics = {
        topic: count - recent_topics.get(topic, 0)
        for topic, count in previous_topics.items()
        if count > recent_topics.get(topic, 0) # 排除在 P1 中计数更高的主题
    }
    
    trend_report = "\n### 📈 主题与关键词趋势分析 (近 7 天 vs 前 7 天)\n"
    trend_report += "对比显示主题和动态关键词的关注度变化，变化率 > 50% 的主题高亮。\n\n"
    
    # 主题趋势
    trend_report += "#### 主题热度变化\n"
    trend_report += "| 主题 | 近 7 天 (P1) | 前 7 天 (P0) | 变化率 | 趋势 |\n"
    trend_report += "| :--- | :---: | :---: | :---: | :---: |\n"
    
    all_topics = set(recent_topics.keys()) | set(p2_only_topics.keys())
    sorted_topics = sorted(list(all_topics), key=lambda x: recent_topics.get(x, 0), reverse=True)

    for topic in sorted_topics:
        count_p1 = recent_topics.get(topic, 0)
        count_p0 = p2_only_topics.get(topic, 0) # 这里使用计算出的 P0 计数
        
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

        if abs(change_rate) > 0.5 and change_rate != float('inf'):
            trend_str = f"**{trend_str}**"
        
        trend_report += f"| {topic} | {count_p1} | {count_p0} | {trend_str} | {trend_icon} |\n"
    
    # 动态关键词趋势
    trend_report += "\n#### 动态关键词 Top 5\n"
    top_keywords = sorted(recent_keywords.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_keywords:
        trend_report += "| 关键词 | 出现次数 |\n"
        trend_report += "| :--- | :---: |\n"
        for keyword, count in top_keywords:
            trend_report += f"| {keyword} | {count} |\n"
    else:
        trend_report += "暂无动态关键词。\n"
    
    return trend_report

# --- 生成统计图表 ---
def generate_stats_chart(analysis: Dict, output_file: str):
    clue_count = len(analysis['investment_clues'])
    lesson_count = len(analysis['experience_lessons'])
    trend_count = len(analysis['industry_trends'])
    
    categories = ['Investment Clues', 'Experience Lessons', 'Industry Trends']
    counts = [clue_count, lesson_count, trend_count]
    
    plt.figure(figsize=(8, 5))
    bars = plt.bar(categories, counts, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
    plt.title('News Analysis Categories Count (Current Run)')
    plt.ylabel('Count')
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.1, int(yval), ha='center', va='bottom')
    plt.savefig(f'{output_file}_stats.png')
    plt.close()
    logger.info(f"Generated stats chart: {output_file}_stats.png")

# --- 生成分析报告 ---
def generate_analysis_report(analysis: Dict, total_count: int, trend_report: str, output_file: str) -> str:
    md_report = "\n---\n"
    md_report += "# 📰 基金投资策略分析报告\n\n"
    md_report += f"本报告根据从 {total_count} 条新闻中提取的高价值信息生成，旨在为您提供 **买入指引、风险规避和行业洞察**。\n\n"

    md_report += "## 📊 统计概述\n"
    md_report += f"- 本次抓取投资线索数量: {len(analysis['investment_clues'])}\n"
    md_report += f"- 本次抓取经验教训数量: {len(analysis['experience_lessons'])}\n"
    md_report += f"- 本次抓取行业趋势数量: {len(analysis['industry_trends'])}\n"
    md_report += f"- 总新闻条目: {total_count}\n"
    # 使用传入的 output_file 参数
    md_report += f"- 生成图表: {output_file}_stats.png, {output_file}_wordcloud.png\n\n" 
    
    md_report += "## 长期趋势分析\n"
    md_report += trend_report

    md_report += "\n## 💰 投资线索与市场焦点 (买入指引)\n"
    if analysis['investment_clues']:
        md_report += "| 焦点标的/策略 | 原始标题 (点击查看) | 权重 |\n"
        md_report += "| :--- | :--- | :---: |\n"
        for clue in analysis['investment_clues']:
            # 修复 Markdown 链接语法
            md_report += f"| **{clue['focus']}** | [{clue['title']}](<{clue['link']}>) | {clue['weight']:.1f} |\n"
    else:
        md_report += "暂无明确的投资线索或机构观点被识别。\n"
        
    md_report += "\n## ⚠️ 投资经验与风险规避 (避免踩坑)\n"
    if analysis['experience_lessons']:
        md_report += "| 教训/经验 | 原始标题 (点击查看) | 权重 |\n"
        md_report += "| :--- | :--- | :---: |\n"
        for lesson in analysis['experience_lessons']:
            # 修复 Markdown 链接语法
            md_report += f"| **{lesson['lesson']}** | [{lesson['title']}](<{lesson['link']}>) | {lesson['weight']:.1f} |\n"
    else:
        md_report += "暂无明确的经验教训或风险提示被识别。\n"

    md_report += "\n## ✨ 行业结构与未来趋势 (长期洞察)\n"
    if analysis['industry_trends']:
        md_report += "| 行业趋势 | 原始标题 (点击查看) | 权重 |\n"
        md_report += "| :--- | :--- | :---: |\n"
        for trend in analysis['industry_trends']:
            # 修复 Markdown 链接语法
            md_report += f"| **{trend['trend']}** | [{trend['title']}](<{trend['link']}>) | {trend['weight']:.1f} |\n"
    else:
        md_report += "暂无明确的行业趋势或结构变化被识别。\n"

    md_report += "\n## 🔍 所有新闻详细分析与潜在影响\n"
    if analysis['detailed_analyses']:
        md_report += "| 新闻标题 | 关键主题 | 情感分析 (得分) | 动态关键词 | 潜在影响 |\n"
        md_report += "| :--- | :--- | :--- | :--- | :--- |\n"
        for det in analysis['detailed_analyses']:
            topics_str = '; '.join(det['key_topics']) if det['key_topics'] else '无特定主题'
            keywords_str = ', '.join(det['dynamic_keywords']) if det['dynamic_keywords'] else '无'
            md_report += f"| {det['title']} | {topics_str} | {det['sentiment']} ({det['sentiment_score']:.1f}) | {keywords_str} | **{det['potential_impact']}** |\n"
    else:
        md_report += "暂无详细分析。\n"

    return md_report

# --- 新增：加载外部配置函数 ---
def load_sources_from_json(file_path: str = 'sources.json') -> List[Dict]:
    """从指定的 JSON 文件中加载数据源配置。"""
    if not os.path.exists(file_path):
        logger.error(f"Configuration file not found: {file_path}. Using empty list.")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sources = json.load(f)
            logger.info(f"Loaded {len(sources)} sources from {file_path}.")
            return sources
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading sources: {e}")
        return []

# ⚠️ 注意：旧的硬编码 sources 列表已从此处移除，以实现配置外置化。

def generate_markdown(news_items: List[Dict], analysis_report: str, timestamp_str: str, configured_sources: List[Dict]) -> str:
    md_content = f"# 基金新闻聚合 ({timestamp_str})\n\n"
    # 从传入的配置列表中提取名称
    source_names = "、".join([s['name'].split('(')[0].strip() for s in configured_sources])
    md_content += f"来源：{source_names}（关键词：基金/实盘/观点/经验/推荐/策略/投资/宏观/金融）。总计 {len(news_items)} 条。\n"
    md_content += analysis_report
    md_content += "\n---\n# 原始新闻列表\n\n"
    for i, item in enumerate(news_items, 1):
        md_content += f"## {i}. {item['title']} ({item['source']})\n"
        md_content += f"- **链接**: [{item['link']}]({item['link']})\n"
        md_content += f"- **时间**: {item['pubDate']}\n"
        md_content += f"- **摘要**: {item['summary']}\n\n"
    return md_content

def main():
    db_manager = DatabaseManager()
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    output_file_base = f'fund_news_{now.strftime("%Y%m%d")}' 
    
    # 💥 关键改动：动态加载 sources 列表
    sources = load_sources_from_json() 
    
    all_news = []
    logger.info(f"[{timestamp_str}] 开始抓取基金新闻 (共 {len(sources)} 个来源)...")
    
    existing_links = db_manager.get_existing_links()
    
    for source in sources:
        logger.info(f"处理来源: {source['name']} ({source['url']})")
        try:
            if source['type'] == 'rss':
                items = fetch_rss_feed(source['url'], source['name'], limit=20)
            else:
                # 确保 Web 源有 selector
                selector = source.get('selector')
                if not selector:
                    logger.error(f"Web source {source['name']} is missing a 'selector' key in sources.json. Skipping.")
                    continue
                items = fetch_web_page(source['url'], source['name'], selector, limit=15)
            all_news.extend(items)
        except Exception as e:
            logger.error(f"Failed to process source {source['name']}: {e}")
            
    unique_news = []
    batch_seen = set()
    for news in all_news:
        link = news.get('link', 'N/A')
        
        # 跨次去重
        if link != 'N/A' and link in existing_links:
            continue
            
        # 批次内去重 (标题+来源)
        if (news['title'], news['source']) not in batch_seen:
            unique_news.append(news)
            batch_seen.add((news['title'], news['source']))
            if link != 'N/A':
                existing_links.add(link) # 提前加入，避免本批次内重复

    # 排序
    unique_news.sort(key=lambda x: datetime.strptime(x['pubDate'], '%Y-%m-%d %H:%M:%S') if x['pubDate'] != 'N/A' else datetime(1900, 1, 1), reverse=True)
    
    analysis_results = analyze_news(unique_news)
    
    # 批量存储新闻
    for item, detailed_analysis in zip(unique_news, analysis_results['detailed_analyses']):
        db_manager.store_news_and_analysis(item, detailed_analysis)
    
    # 生成词云 (已修复 OSEerror)
    recent_keywords = db_manager.get_dynamic_keywords_by_time_range(days=7)
    generate_wordcloud(recent_keywords, output_file_base)
    
    # 生成报告
    trend_report_md = generate_trend_analysis(db_manager)
    analysis_report_md = generate_analysis_report(analysis_results, len(unique_news), trend_report_md, output_file_base) 
    generate_stats_chart(analysis_results, output_file_base)
    
    # 修复：将 sources 列表作为参数传入 generate_markdown
    md_content = generate_markdown(unique_news, analysis_report_md, timestamp_str, sources)
    
    with open(f'{output_file_base}.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    logger.info(f"收集到 {len(unique_news)} 条独特基金新闻。分析报告已生成并保存至 {output_file_base}.md")
    logger.info("\n--- 分析报告摘要 ---")
    logger.info(analysis_report_md.split('## 💰')[0])
    
    db_manager.close()

if __name__ == "__main__":
    main()
