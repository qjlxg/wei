import os
import datetime
import time
from pathlib import Path
from urllib.parse import quote
import re
# 以下导入已被移除：from selenium import webdriver, from selenium.webdriver.chrome.options import Options, from bs4 import BeautifulSoup, from selenium.webdriver.support.ui import WebDriverWait, from selenium.webdriver.support import expected_conditions as EC, from selenium.webdriver.common.by import By, import random
import json
import jieba
from snownlp import SnowNLP
import requests # 新增 requests 库
import random # 确保 random 库被导入

# MCP Server 配置
MCP_SERVER_URL = "http://localhost:3000/api/tools/search_content"
DEFAULT_LIMIT = 50  # MCP服务器默认返回的条数，可根据需要调整

# --- 辅助函数：提取热门基金类型 (功能保留) ---
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


# --- 辅助函数：时间解析 (功能保留) ---
def parse_absolute_time(time_str):
    """
    Parses relative Weibo time strings (e.g., '2小时前', '今天 10:00') into absolute datetime objects.
    """
    now = datetime.datetime.now()
    time_str = time_str.strip()
    
    # 刚刚/分钟前
    if '刚刚' in time_str:
        return now - datetime.timedelta(seconds=random.randint(10, 59))
        
    elif '分钟前' in time_str:
        try:
            minutes = int(re.search(r'(\d+)', time_str).group(1))
            return now - datetime.timedelta(minutes=minutes)
        except:
            return now
            
    # 小时前
    elif '小时前' in time_str:
        try:
            hours = int(re.search(r'(\d+)', time_str).group(1))
            return now - datetime.timedelta(hours=hours)
        except:
            return now

    # 今天 XX:XX
    elif '今天' in time_str:
        try:
            time_part = time_str.split(' ')[-1]
            return datetime.datetime.strptime(f"{now.date()} {time_part}", '%Y-%m-%d %H:%M')
        except:
            return now.replace(minute=0, second=0, microsecond=0)
            
    # MM-DD
    elif re.match(r'\d{2}-\d{2}', time_str): 
        try:
            year = now.year
            # 如果解析后的日期比当前日期晚，则年份应为去年
            parsed_date = datetime.datetime.strptime(f"{year}-{time_str}", '%Y-%m-%d')
            if parsed_date > now:
                parsed_date = datetime.datetime.strptime(f"{year-1}-{time_str}", '%Y-%m-%d')
            return parsed_date.replace(hour=12, minute=0, second=0, microsecond=0)
        except:
            return now.date()

    # YYYY-MM-DD
    try:
        return datetime.datetime.strptime(time_str, '%Y-%m-%d')
    except:
        # Fallback to current time if parsing fails
        return now.date()
        

# --- 辅助函数：基金类型分类 (功能保留) ---
def get_fund_type(content):
    """
    Categorizes the tweet based on fund sector keywords.
    """
    content_lower = content.lower()
    patterns = {
        r'中药|cxo|医疗|医药|创新药': '医药/医疗基金',
        r'芯片|半导体|集成电路|科技|信息技术': '半导体/科技基金',
        r'锂电|风电|光伏|新能源|电动车|碳中和': '新能源/光伏基金',
        r'etf|指数|沪深300|中证500|纳斯达克|标普': 'ETF/指数基金',
        r'fof': 'FOF',
        r'证券|券商|保险|银行|金融': '证券/金融基金',
        r'私募|私募基金|信托': '私募基金',
        r'消费|白酒|食品|家电|免税': '消费基金',
        r'军工|国防|大宗商品|资源|煤炭|有色': '军工/资源基金',
        r'港股|恒生|中概股': '港股/中概股基金'
    }
    for pattern, fund_type in patterns.items():
        if re.search(pattern, content_lower):
            return fund_type
    return '通用基金'

# --- 辅助函数：推文内容分类 (功能保留) ---
def categorize_tweet(content):
    """
    Categorizes the tweet based on the action/topic discussed.
    """
    content_lower = content.lower()
    categories = []
    
    if re.search(r'(加仓|买入|卖出|持仓|调仓|交易|实盘|做t|定投|清仓|赎回)', content_lower):
        categories.append('个人实盘/买卖记录')
    if re.search(r'(心得|经验|体会|感悟|总结|分享|教训)', content_lower):
        categories.append('心得/经验/体会')
    if re.search(r'(分析|拆解|解读|诊断|收益|净值|策略|目标价|估值)', content_lower):
        categories.append('分析')
    if re.search(r'(政策|法规|监管|央行|证监会|持有人大会|私募|公募|降准|降息)', content_lower):
        categories.append('国家政策/法规')
    if re.search(r'(宏观|微观|周期|趋势|震荡|回调|底部|风险|见顶|高位)', content_lower):
        categories.append('宏观/微观影响')
    if re.search(r'(国内|国际|全球|市场|A股|美股|欧股)', content_lower):
        categories.append('国内/国际影响')
    
    return categories if categories else ['其他']

# --- 辅助函数：关键词提取 (功能保留) ---
def extract_keywords(tweets, top_n=5):
    """
    Extracts and counts keywords from all tweets using jieba, returns top N.
    """
    all_text = " ".join(t['content'] for t in tweets)
    stopwords = set([
        '基金', '今天', '明天', '操作', '大家', '就是', '这个', '一个', '已经', '自己', 
        '的', '是', '了', '啊', '我', '你', '他', '她', '它', '和', '在', '对', '有', 
        '都', '可以', '需要', '如果', '我们', '你们', '他们', '这些', '那些', '不是', 
        '没有', '什么', '所以', '去', '来', '跟', '被', '把', '但', '也', '还', '会', '能', '要',
        '不能', '不会', '不要', '很好', '非常', '比较', '可能', '一定'
    ])
    
    words = jieba.cut(all_text)
    word_counts = {}
    
    for word in words:
        word = word.lower().strip()
        # 仅统计长度大于1且不在停用词表中的词
        if len(word) > 1 and word not in stopwords:
            word_counts[word] = word_counts.get(word, 0) + 1
            
    sorted_keywords = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    return [kw[0] for kw in sorted_keywords[:top_n]]


# --- 核心修改：使用 requests 调用 MCP Server API ---
def fetch_weibo_data(keyword, pages=2):
    """
    Fetch Weibo posts by calling the local mcp-server-weibo API.
    
    :param keyword: The search term.
    :param pages: Approximate number of pages to fetch (converted to a single limit for MCP).
    :return: List of processed tweets.
    """
    tweets = []
    
    # 我们将 pages 参数转化为单个请求的 limit 参数: total_limit = pages * DEFAULT_LIMIT
    total_limit = pages * DEFAULT_LIMIT
    
    # 请求参数与 mcp-server-weibo 的 search_content(keyword, limit, page?) 工具函数对应
    payload = {
        "keyword": keyword,
        "limit": total_limit,
        "page": 1 # 简化为一次性请求足够多的数据
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Attempting to fetch data from MCP Server: {MCP_SERVER_URL} with keyword '{keyword}' and limit {total_limit}")
    
    try:
        # 尝试连接 MCP Server，增加 timeout 以防止卡住
        response = requests.post(MCP_SERVER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # 检查 HTTP 错误
        
        # 解析 MCP Server 返回的 JSON 结构
        response_json = response.json()
        
        # 如果 MCP Server 返回了错误信息
        if 'error' in response_json or (response_json.get('status') == 'error'):
             error_msg = response_json.get('error', response_json.get('message', 'Unknown error'))
             print(f"MCP Server returned an error: {error_msg}")
             return []
             
        # 提取微博列表
        raw_weibo_list = response_json.get('data') or response_json.get('results') or []

        if not raw_weibo_list:
            print("MCP Server returned an empty list of results.")
            return []

        # 处理和清洗数据
        for item in raw_weibo_list:
            # 假设 MCP Server 返回的结构包含 text/content, user/username, created_at/time, url/link
            content = item.get('text', item.get('content', ''))
            
            # 过滤掉内容为空或过短的微博
            if not content or len(content.strip()) < 10:
                continue

            user = item.get('user', {}).get('screen_name', item.get('username', 'Unknown'))
            raw_time = item.get('created_at', item.get('time', datetime.datetime.now().strftime('%Y-%m-%d %H:%M')))
            link = item.get('url', MCP_SERVER_URL) # 如果没有链接，使用服务器URL作为回退
            
            absolute_time = parse_absolute_time(raw_time)
            sentiment_score = SnowNLP(content).sentiments
            
            tweet = {
                'user': user,
                'time': raw_time,
                'absolute_time': absolute_time.strftime('%Y-%m-%d %H:%M:%S'),
                'content': content.strip(),
                'link': link,
                'fund_type': get_fund_type(content),
                'categories': categorize_tweet(content),
                'sentiment': round(sentiment_score, 4)
            }
            tweets.append(tweet)
            
        print(f"Successfully fetched {len(tweets)} tweets via MCP Server.")
        
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Connection Error (Is MCP Server running?): {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected Request Error occurred: {err}")
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
        
    return tweets


# --- 报告生成和保存函数 (功能保留) ---
def generate_report(keyword, tweets):
    """
    Generates a detailed markdown report based on the processed tweets.
    """
    timestamp = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    
    if not tweets:
        return f"# 基金相关微博内容报告\n\n**生成时间**：{timestamp}\n**关键词**：{keyword}\n**数据来源**：未抓取到任何数据。\n\n## 关键洞察与趋势\n- **建议**：请检查 mcp-server-weibo 服务的运行状态。\n"
        
    avg_sentiment = sum(t['sentiment'] for t in tweets) / len(tweets)
    sentiment_label = "积极" if avg_sentiment > 0.6 else ("消极" if avg_sentiment < 0.4 else "中性")
    top_keywords = extract_keywords(tweets)
        
    report_lines = [
        f"# 基金相关微博内容报告\n\n**生成时间**：{timestamp}  \n**关键词**：{keyword}  \n**数据来源**：基于微博搜索结果，提取{len(tweets)}条内容 (通过 MCP Server 接口)。  \n\n- **情感指数**：基于SnowNLP分析，整体情绪{sentiment_label} (均值：{avg_sentiment:.4f})  \n- **热门关键词**：{', '.join(top_keywords)}  \n\n## 1. 原始帖子/文章列表（Top {len(tweets)} 精选）\n以下按时间倒序。",
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
        sentiment_display = f"{'积极' if tweet['sentiment'] > 0.6 else ('消极' if tweet['sentiment'] < 0.4 else '中性')}({tweet['sentiment']:.2f})"
        report_lines.append(f"| {i} | {tweet['user']} | {tweet['time']} | {tweet['absolute_time'][:16]} | {content_snippet.replace('|', '/')} | {sentiment_display} | [🔗]({tweet['link']}) |\n")
    
    
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
        if re.search(r'(卖出|清仓|赎回)', content_lower): buy_sell['sell'].append(tweet)
        if re.search(r'(持仓|持有|定投)', content_lower): buy_sell['hold'].append(tweet)
        if re.search(r'(调仓|调整|暂停)', content_lower): buy_sell['adjust'].append(tweet)
    
    
    report_lines.append("\n## 2. 分类整理\n按类别分组，相同基金/主题汇总。")
    for category, cat_tweets in categories.items():
        if cat_tweets:
            cat_sentiment = sum(t['sentiment'] for t in cat_tweets) / len(cat_tweets)
            cat_label = "积极" if cat_sentiment > 0.6 else ("消极" if cat_sentiment < 0.4 else "中性")
            report_lines.append(f"\n### {category} ({len(cat_tweets)} posts) - 情绪: {cat_label} (均值: {cat_sentiment:.2f})")
            for tweet in cat_tweets[:5]: # 仅显示前5条
                content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
                sentiment_status = '积极' if tweet['sentiment'] > 0.6 else ('消极' if tweet['sentiment'] < 0.4 else '中性')
                report_lines.append(f"- **{tweet['fund_type']}** ({sentiment_status}): {tweet['user']} ({tweet['time']}): {content_snippet} [🔗]({tweet['link']})\n")
    
    
    report_lines.append("\n## 3. 按基金类型分组")
    for fund_type, group_tweets in sorted(fund_groups.items(), key=lambda item: len(item[1]), reverse=True):
        if len(group_tweets) < 3 and fund_type == '通用基金': # 过滤掉通用基金中数量过少的
             continue
        group_sentiment = sum(t['sentiment'] for t in group_tweets) / len(group_tweets)
        group_label = "积极" if group_sentiment > 0.6 else ("消极" if group_sentiment < 0.4 else "中性")
        report_lines.append(f"\n### {fund_type} ({len(group_tweets)} posts) - 情绪: {group_label} (均值: {group_sentiment:.2f})")
        for tweet in group_tweets[:5]: # 仅显示前5条
            content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
            report_lines.append(f"- {tweet['user']} ({tweet['time']}): {content_snippet} [🔗]({tweet['link']})\n")
    
    
    report_lines.append("\n## 4. 买卖/持仓/调仓对比")
    for action, action_tweets in buy_sell.items():
        if action_tweets:
            action_name = action.capitalize()
            action_sentiment = sum(t['sentiment'] for t in action_tweets) / len(action_tweets)
            action_label = "积极" if action_sentiment > 0.6 else ("消极" if action_sentiment < 0.4 else "中性")
            report_lines.append(f"\n### {action_name} ({len(action_tweets)} posts) - 情绪: {action_label} (均值: {action_sentiment:.2f})")
            top_funds = get_top_fund_types(action_tweets, n=2)
            funds_str = '、'.join(top_funds) if top_funds else '无明显热点'
            report_lines.append(f"**热点基金**：{funds_str}\n")
            
            for tweet in action_tweets[:3]: # 仅显示前3条
                content_snippet = tweet['content'][:60] + '...' if len(tweet['content']) > 60 else tweet['content']
                report_lines.append(f"- **{tweet['fund_type']}**: {tweet['user']}: {content_snippet} [🔗]({tweet['link']})\n")
    
    
    trends = []
    if buy_sell['buy']:
        top_buy_funds = get_top_fund_types(buy_sell['buy'], n=2)
        if top_buy_funds:
            funds_str = '、'.join(top_buy_funds)
            trends.append(f"**加仓热点**：数据显示，用户对 **{funds_str}** 基金操作最积极，表现出买入/加仓倾向。")
        else:
            trends.append("买入/加仓操作较分散，暂无明显热点基金。")

    if buy_sell['sell'] or buy_sell['adjust']:
        all_sell_adjust = buy_sell['sell'] + buy_sell['adjust']
        top_sell_funds = get_top_fund_types(all_sell_adjust, n=2)
        if top_sell_funds:
            funds_str = '、'.join(top_sell_funds)
            trends.append(f"**调仓风险**：**{funds_str}** 基金的卖出/调仓行为最为集中，需关注潜在回调风险。")
        else:
            trends.append("卖出/调仓操作较分散，但用户有进行风险调整的行为。")

    if buy_sell['hold']:
        top_hold_funds = get_top_fund_types(buy_sell['hold'], n=1)
        funds_str = '、'.join(top_hold_funds) if top_hold_funds else '多只基金'
        trends.append(f"**持仓风格**：用户强调对 **{funds_str}** 的长期定投或持有策略。")

    policy_macro_tweets = categories['国家政策/法规'] + categories['宏观/微观影响']
    if policy_macro_tweets:
        policy_keywords = extract_keywords(policy_macro_tweets, top_n=3)
        keywords_str = '、'.join(policy_keywords) if policy_keywords else '政策或宏观经济'
        trends.append(f"**政策影响**：讨论集中在 **{keywords_str}** 等关键词，显示政策驱动或宏观变化是重要关注点。")
    
    
    enhanced_trends = [
        f"**情感概览**: 整体情绪倾向于{sentiment_label} (均值: {avg_sentiment:.2f})。",
        f"**热门关键词**: 本期讨论中，**{', '.join(top_keywords)}** 词频最高，显示市场焦点集中于此。",
        f"**交易行为**: {' '.join(trends) if trends else '暂无明显交易趋势'}"
    ]
    
    trends_content = '\n'.join([f'- {t}' for t in enhanced_trends])
    report_lines.append(f"\n## 5. 关键洞察与趋势\n{trends_content}\n- **建议**：报告基于公开片段的自动分析，请务必检查 mcp-server-weibo 的运行情况。\n")
    
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
    
    if not tweets:
        print("Scraper returned 0 tweets. Exiting script as there is no data to report.")
        return 

    save_json_data(tweets) 
    
    report_content = generate_report(keyword, tweets)
    save_report(report_content)

if __name__ == "__main__":
    main()
