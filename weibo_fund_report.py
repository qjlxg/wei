import os
import datetime
import time
from pathlib import Path
from urllib.parse import quote
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json
import jieba
from snownlp import SnowNLP 
# --- 新增 Selenium 显式等待所需模块 ---
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


# --- 辅助函数：提取热门基金类型 ---
def get_top_fund_types(tweets, n=2):
    """
    Counts fund types in a list of tweets and returns the top N most frequent ones.
    Excludes '通用基金' from being the specific top type.
    """
    if not tweets:
        return []
        
    fund_counts = {}
    for tweet in tweets:
        fund_type = tweet['fund_type']
        fund_counts[fund_type] = fund_counts.get(fund_type, 0) + 1
    
    # 移除或降低“通用基金”的优先级，因为它缺乏特异性
    if '通用基金' in fund_counts:
        del fund_counts['通用基金']
        
    sorted_funds = sorted(fund_counts.items(), key=lambda item: item[1], reverse=True)
    return [f[0] for f in sorted_funds[:n]]


def parse_absolute_time(time_str):
    """
    Parses relative Weibo time strings (e.g., '2小时前', '今天 10:00') into absolute datetime objects.
    """
    now = datetime.datetime.now()
    time_str = time_str.strip()
    
    if '今天' in time_str:
        try:
            time_part = time_str.split(' ')[-1]
            return datetime.datetime.strptime(f"{now.date()} {time_part}", '%Y-%m-%d %H:%M')
        except:
            return now.replace(minute=0, second=0, microsecond=0)
            
    elif '分钟前' in time_str:
        try:
            minutes = int(re.search(r'(\d+)', time_str).group(1))
            return now - datetime.timedelta(minutes=minutes)
        except:
            return now
            
    elif '小时前' in time_str:
        try:
            hours = int(re.search(r'(\d+)', time_str).group(1))
            return now - datetime.timedelta(hours=hours)
        except:
            return now
            
    elif re.match(r'\d{2}-\d{2}', time_str): # Example: '09-27'
        try:
            year = now.year
            return datetime.datetime.strptime(f"{year}-{time_str}", '%Y-%m-%d')
        except:
            return now.date()

    try:
        return datetime.datetime.strptime(time_str, '%Y-%m-%d')
    except:
        return now.date()


def fetch_weibo_data(keyword, pages=2):
    """
    Fetch Weibo posts from https://s.weibo.com using Selenium to handle dynamic content.
    Returns a list of tweets with user, time, content, link, fund_type, categories, and sentiment.
    --- 关键优化：使用显式等待并抓取所有帖子 ---
    """
    tweets = []
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    driver = webdriver.Chrome(options=options)
    
    for page in range(1, pages + 1):
        search_url = f"https://s.weibo.com/weibo?q={quote(keyword)}&page={page}"
        try:
            driver.get(search_url)
            
            # --- 优化：使用显式等待代替 time.sleep() ---
            # 等待主要的微博列表容器加载完成，最多等待 15 秒
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.card-wrap'))
            )
            
            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            # 抓取页面上的所有帖子，不限制数量
            cards = soup.find_all('div', {'action-type': 'feed_list_item'}) or soup.find_all('div', class_='card-wrap')
            
            for card in cards:
                user_elem = card.find('a', class_='name') or card.find('strong', class_='WB_text')
                time_elem = card.find('div', class_='from') or card.select_one('[node-type="feed_list_content"] time')
                link_elem = card.find('a', href=re.compile(r'/weibo/.*'))
                content_elem = card.find('p', class_='txt') or card.find('div', class_='WB_text')
                
                content = content_elem.get_text(strip=True) if content_elem else 'No content'
                if len(content) < 10:  # Skip invalid content
                    continue
                
                raw_time = time_elem.text.strip() if time_elem else datetime.datetime.now().strftime('%Y-%m-%d')
                absolute_time = parse_absolute_time(raw_time)
                sentiment_score = SnowNLP(content).sentiments
                
                tweet = {
                    'user': user_elem.text.strip() if user_elem else 'Unknown',
                    'time': raw_time,
                    'absolute_time': absolute_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'content': content,
                    'link': 'https://s.weibo.com' + link_elem['href'] if link_elem else search_url,
                    'fund_type': get_fund_type(content),
                    'categories': categorize_tweet(content),
                    'sentiment': round(sentiment_score, 4)
                }
                tweets.append(tweet)
            
            print(f"Fetched {len(cards)} tweets from page {page}")
            
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue
    
    driver.quit()
    return tweets

def categorize_tweet(content):
    """
    Auto-categorize content using keyword matching (multi-label).
    """
    content_lower = content.lower()
    categories = []
    
    if re.search(r'(加仓|买入|卖出|持仓|调仓|交易|实盘|做t|定投|清仓)', content_lower):
        categories.append('个人实盘/买卖记录')
    if re.search(r'(心得|经验|体会|感悟|总结|分享|教训)', content_lower):
        categories.append('心得/经验/体会')
    if re.search(r'(分析|拆解|解读|诊断|收益|净值|策略)', content_lower):
        categories.append('分析')
    if re.search(r'(政策|法规|监管|央行|证监会|持有人大会|私募|公募)', content_lower):
        categories.append('国家政策/法规')
    if re.search(r'(宏观|微观|周期|趋势|震荡|回调|底部|风险)', content_lower):
        categories.append('宏观/微观影响')
    if re.search(r'(国内|国际|全球|市场|A股)', content_lower):
        categories.append('国内/国际影响')
    
    return categories if categories else ['其他']

def get_fund_type(content):
    """
    Auto-detect fund type based on content.
    """
    content_lower = content.lower()
    patterns = {
        r'中药|cxo|医疗|医药': '医药/医疗基金',
        r'芯片|半导体|集成电路': '半导体基金',
        r'锂电|风电|光伏|新能源|电动车': '新能源/光伏基金',
        r'etf|指数|沪深300|中证500': 'ETF/指数基金',
        r'fof': 'FOF',
        r'证券|券商|保险': '证券/金融基金',
        r'私募|私募基金': '私募基金',
        r'消费|白酒': '消费基金'
    }
    for pattern, fund_type in patterns.items():
        if re.search(pattern, content_lower):
            return fund_type
    return '通用基金'

def extract_keywords(tweets, top_n=5):
    """
    使用 Jieba 进行分词和关键词提取。
    """
    all_text = " ".join(t['content'] for t in tweets)
    stopwords = set([
        '基金', '今天', '明天', '操作', '大家', '就是', '这个', '一个', '已经', '自己', 
        '的', '是', '了', '啊', '我', '你', '他', '她', '它', '和', '在', '对', '有', 
        '都', '可以', '需要', '如果', '我们', '你们', '他们', '我们'
    ])
    
    words = jieba.cut(all_text)
    word_counts = {}
    
    for word in words:
        word = word.lower().strip()
        if len(word) > 1 and word not in stopwords:
            word_counts[word] = word_counts.get(word, 0) + 1
            
    sorted_keywords = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    return [kw[0] for kw in sorted_keywords[:top_n]]

def generate_report(keyword, tweets):
    """
    Generate structured Markdown report with dynamic trend analysis.
    """
    timestamp = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    
    avg_sentiment = sum(t['sentiment'] for t in tweets) / len(tweets)
    sentiment_label = "积极" if avg_sentiment > 0.6 else ("消极" if avg_sentiment < 0.4 else "中性")
    top_keywords = extract_keywords(tweets)
        
    report_lines = [
        f"# 基金相关微博内容报告\n\n**生成时间**：{timestamp}  \n**关键词**：{keyword}  \n**数据来源**：基于微博搜索结果，提取{len(tweets)}条内容。  \n\n- **情感指数**：基于SnowNLP分析，整体情绪{sentiment_label} (均值：{avg_sentiment:.4f})  \n- **热门关键词**：{', '.join(top_keywords)}  \n\n## 1. 原始帖子/文章列表（Top {len(tweets)} 精选）\n以下按时间倒序。",
        "| # | 用户/来源 | 时间（估算） | 归一化时间 | 内容要点 | 情感 | 链接/来源 |\n|---|-----------|-------------|------------|----------|------|-----------|\n"
    ]
    
    def parse_sort_time(t):
        try:
            return datetime.datetime.strptime(t['absolute_time'], '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.datetime.now()
    
    sorted_tweets = sorted(tweets, key=parse_sort_time, reverse=True)
    
    for i, tweet in enumerate(sorted_tweets, 1):
        content_snippet = tweet['content'][:100] + '...' if len(tweet['content']) > 100 else tweet['content']
        sentiment_display = f"{'积极' if tweet['sentiment'] > 0.6 else ('消极' if tweet['sentiment'] < 0.4 else '中性')}({tweet['sentiment']})"
        report_lines.append(f"| {i} | {tweet['user']} | {tweet['time']} | {tweet['absolute_time'][:16]} | {content_snippet} | {sentiment_display} | [{tweet['link']}]({tweet['link']}) |\n")
    
    
    categories = {
        '个人实盘/买卖记录': [], '心得/经验/体会': [], '分析': [], '国家政策/法规': [],
        '宏观/微观影响': [], '国内/国际影响': [], '其他': []
    }
    fund_groups = {}
    buy_sell = {'buy': [], 'sell': [], 'hold': [], 'adjust': []}
    
    for tweet in tweets:
        fund_type = tweet['fund_type']
        if fund_type not in fund_groups:
            fund_groups[fund_type] = []
        fund_groups[fund_type].append(tweet)
        
        for cat in tweet['categories']:
            if cat in categories:
                categories[cat].append(tweet)
        
        content_lower = tweet['content'].lower()
        if re.search(r'(加仓|买入)', content_lower): buy_sell['buy'].append(tweet)
        if re.search(r'(卖出|清仓)', content_lower): buy_sell['sell'].append(tweet)
        if re.search(r'(持仓|持有|定投)', content_lower): buy_sell['hold'].append(tweet)
        if re.search(r'(调仓|调整|暂停)', content_lower): buy_sell['adjust'].append(tweet)
    
    
    report_lines.append("\n## 2. 分类整理\n按类别分组，相同基金/主题汇总。")
    for category, cat_tweets in categories.items():
        if cat_tweets:
            cat_sentiment = sum(t['sentiment'] for t in cat_tweets) / len(cat_tweets)
            cat_label = "积极" if cat_sentiment > 0.6 else ("消极" if cat_sentiment < 0.4 else "中性")
            report_lines.append(f"\n### {category} ({len(cat_tweets)} posts) - 情绪: {cat_label}")
            for tweet in cat_tweets:
                content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
                sentiment_status = '积极' if tweet['sentiment'] > 0.6 else ('消极' if tweet['sentiment'] < 0.4 else '中性')
                report_lines.append(f"- **{tweet['fund_type']}** ({sentiment_status}): {tweet['user']} ({tweet['time']}): {content_snippet} [链接]({tweet['link']})\n")
    
    
    report_lines.append("\n## 按基金类型分组")
    for fund_type, group_tweets in fund_groups.items():
        report_lines.append(f"\n### {fund_type} ({len(group_tweets)} posts)")
        for tweet in group_tweets:
            content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
            report_lines.append(f"- {tweet['user']} ({tweet['time']}): {content_snippet} [链接]({tweet['link']})\n")
    
    
    report_lines.append("\n## 买卖/持仓/调仓对比")
    for action, action_tweets in buy_sell.items():
        if action_tweets:
            action_name = action.capitalize()
            report_lines.append(f"\n### {action_name} ({len(action_tweets)} posts)")
            for tweet in action_tweets:
                content_snippet = tweet['content'][:60] + '...' if len(tweet['content']) > 60 else tweet['content']
                report_lines.append(f"- **{tweet['fund_type']}**: {tweet['user']}: {content_snippet} [链接]({tweet['link']})\n")
    
    
    # --- 动态趋势分析：彻底替换假设性结论 ---
    trends = []
    
    # 1. 动态分析“买入/加仓”热点
    if buy_sell['buy']:
        top_buy_funds = get_top_fund_types(buy_sell['buy'], n=2)
        if top_buy_funds:
            funds_str = '、'.join(top_buy_funds)
            trends.append(f"**加仓热点**：数据显示，用户对 **{funds_str}** 基金操作最积极，表现出买入/加仓倾向。")
        else:
            trends.append("买入/加仓操作较分散，暂无明显热点基金。")

    # 2. 动态分析“卖出/调仓”风险
    if buy_sell['sell'] or buy_sell['adjust']:
        all_sell_adjust = buy_sell['sell'] + buy_sell['adjust']
        top_sell_funds = get_top_fund_types(all_sell_adjust, n=2)
        if top_sell_funds:
            funds_str = '、'.join(top_sell_funds)
            trends.append(f"**调仓风险**：**{funds_str}** 基金的卖出/调仓行为最为集中，需关注潜在回调风险。")
        else:
            trends.append("卖出/调仓操作较分散，但用户有进行风险调整的行为。")

    # 3. 动态分析“持仓”和“政策”趋势
    if buy_sell['hold']:
        top_hold_funds = get_top_fund_types(buy_sell['hold'], n=1)
        funds_str = '、'.join(top_hold_funds) if top_hold_funds else '多只基金'
        trends.append(f"**持仓风格**：用户强调对 **{funds_str}** 的长期定投或持有策略。")

    policy_macro_tweets = categories['国家政策/法规'] + categories['宏观/微观影响']
    if policy_macro_tweets:
        policy_keywords = extract_keywords(policy_macro_tweets, top_n=3)
        keywords_str = '、'.join(policy_keywords) if policy_keywords else '政策或宏观经济'
        trends.append(f"**政策影响**：讨论集中在 **{keywords_str}** 等关键词，显示政策驱动或宏观变化是重要关注点。")
    
    
    # --- 整合总结 ---
    enhanced_trends = [
        f"**情感概览**: 整体情绪倾向于{sentiment_label} (均值: {avg_sentiment:.2f})。",
        f"**热门关键词**: 本期讨论中，**{', '.join(top_keywords)}** 词频最高，显示市场焦点集中于此。",
        f"**交易行为**: {' '.join(trends) if trends else '暂无明显交易趋势'}"
    ]
    
    trends_content = '\n'.join([f'- {t}' for t in enhanced_trends])
    report_lines.append(f"\n## 3. 关键洞察与趋势\n{trends_content}\n- **建议**：报告基于公开片段的自动分析，建议结合专业的基金诊断工具，并关注政策变化。\n")
    
    return ''.join(report_lines)

def save_json_data(tweets, output_path="reports"):
    """
    保存原始数据到 JSON 文件。
    """
    Path(output_path).mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_path}/weibo_fund_data_{timestamp}.json"
    
    serializable_tweets = [
        {k: v for k, v in t.items()} for t in tweets
    ]
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(serializable_tweets, f, ensure_ascii=False, indent=4)
    print(f"Raw data saved to {filename}")
    return filename


def save_report(report_content, output_path="reports"):
    """
    Save the report to a Markdown file.
    """
    Path(output_path).mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_path}/weibo_fund_report_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Report saved to {filename}")
    return filename

def main():
    keyword = os.getenv("WEIBO_KEYWORD", "基金")
    tweets = fetch_weibo_data(keyword)
    
    # --- 如果抓取为空则直接退出，避免生成空文件 ---
    if not tweets:
        print("Scraper returned 0 tweets. Exiting script as there is no data to report.")
        return 

    save_json_data(tweets) 
    
    report_content = generate_report(keyword, tweets)
    save_report(report_content)

if __name__ == "__main__":
    main()
