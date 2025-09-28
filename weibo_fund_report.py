import os
import datetime
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import quote
import re

def fetch_weibo_data(keyword, pages=3):
    """
    Fetch Weibo posts from https://s.weibo.com for the keyword.
    Returns a list of tweets with user, time, content, link, fund_type, categories.
    """
    tweets = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for page in range(1, pages + 1):
        search_url = f"https://s.weibo.com/weibo?q={quote(keyword)}&page={page}"
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Improved selector for Weibo posts
            cards = soup.find_all('div', {'action-type': 'feed_list_item'}) or soup.find_all('div', class_='card-wrap')
            for card in cards[:5]:  # Limit to 5 posts per page to avoid overload
                user_elem = card.find('a', class_='name') or card.find('strong', class_='WB_text')
                time_elem = card.find('div', class_='from') or card.select_one('[node-type="feed_list_content"] time')
                content_elem = card.find('p', class_='txt') or card.find('div', class_='WB_text')
                link_elem = card.find('a', href=re.compile(r'/weibo/.*'))
                
                content = content_elem.get_text(strip=True) if content_elem else 'No content'
                if len(content) < 10:  # Skip invalid or short content
                    continue
                
                tweet = {
                    'user': user_elem.text.strip() if user_elem else 'Unknown',
                    'time': time_elem.text.strip() if time_elem else datetime.datetime.now().strftime('%Y-%m-%d'),
                    'content': content,
                    'link': 'https://s.weibo.com' + link_elem['href'] if link_elem else search_url,
                    'fund_type': get_fund_type(content),
                    'categories': categorize_tweet(content)
                }
                tweets.append(tweet)
            
            print(f"Fetched {len(cards[:5])} tweets from page {page}")
            time.sleep(3)  # Increased delay to avoid rate limiting
            
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue
    
    return tweets

def categorize_tweet(content):
    """
    Auto-categorize content using keyword matching (multi-label).
    """
    content_lower = content.lower()
    categories = []
    
    # Personal trading records
    if re.search(r'(加仓|买入|卖出|持仓|调仓|交易|实盘|做t|定投|清仓)', content_lower):
        categories.append('个人实盘/买卖记录')
    
    # Insights/experience
    if re.search(r'(心得|经验|体会|感悟|总结|分享|教训)', content_lower):
        categories.append('心得/经验/体会')
    
    # Analysis
    if re.search(r'(分析|拆解|解读|诊断|收益|净值|策略)', content_lower):
        categories.append('分析')
    
    # Policy/regulations
    if re.search(r'(政策|法规|监管|央行|证监会|持有人大会|私募|公募)', content_lower):
        categories.append('国家政策/法规')
    
    # Macro/micro impacts
    if re.search(r'(宏观|微观|周期|趋势|震荡|回调|底部|风险)', content_lower):
        categories.append('宏观/微观影响')
    
    # Domestic/international impacts
    if re.search(r'(国内|国际|全球|市场|A股)', content_lower):
        categories.append('国内/国际影响')
    
    return categories if categories else ['其他']

def get_fund_type(content):
    """
    Auto-detect fund type based on content.
    """
    content_lower = content.lower()
    patterns = {
        r'医疗|医药': '医疗基金',
        r'半导体|芯片': '半导体基金',
        r'光伏|新能源': '新能源/光伏基金',
        r'etf|指数': 'ETF/指数基金',
        r'fof': 'FOF',
        r'证券|券商': '证券基金',
        r'私募': '私募基金'
    }
    for pattern, fund_type in patterns.items():
        if re.search(pattern, content_lower):
            return fund_type
    return '通用基金'

def generate_report(keyword, tweets):
    """
    Generate structured Markdown report with auto-classification.
    """
    timestamp = datetime.datetime.now().strftime("%Y年%m月%d日")
    report_lines = [
        f"# 基金相关微博内容报告\n\n**生成时间**：{timestamp}  \n**关键词**：{keyword}（聚焦实盘、买卖记录、心得/经验/体会、分析、国家政策/法规、宏观/微观、国内/国际影响）  \n**数据来源**：基于微博搜索结果（https://s.weibo.com），提取{len(tweets)}条内容。结果动态，可能需登录查看完整。报告自动分类整理：  \n- **相同基金/主题分组**：突出买卖对比、持仓、调仓、做T、交易记录。  \n- **分类**：自动多标签分类。  \n- **关键趋势**：自动总结热点。\n\n## 1. 原始帖子/文章列表（Top {len(tweets)} 精选）\n以下按时间倒序。",
        "| # | 用户/来源 | 时间（估算） | 内容要点 | 链接/来源 |\n|---|-----------|-------------|----------|-----------|\n"
    ]
    
    # Sort tweets by time (most recent first, handling non-standard time formats)
    def parse_time(t):
        try:
            return datetime.datetime.strptime(t, '%Y-%m-%d')
        except:
            return datetime.datetime.now()  # Fallback for relative times like "2小时前"
    
    sorted_tweets = sorted(tweets, key=lambda x: parse_time(x['time']), reverse=True)
    for i, tweet in enumerate(sorted_tweets, 1):
        content_snippet = tweet['content'][:100] + '...' if len(tweet['content']) > 100 else tweet['content']
        report_lines.append(f"| {i} | {tweet['user']} | {tweet['time']} | {content_snippet} | [{tweet['link']}]({tweet['link']}) |\n")
    
    # Group by categories and fund types
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
        
        # Buying/selling/holding/adjusting comparison
        content_lower = tweet['content'].lower()
        if re.search(r'(加仓|买入)', content_lower): buy_sell['buy'].append(tweet)
        if re.search(r'(卖出|清仓)', content_lower): buy_sell['sell'].append(tweet)
        if re.search(r'(持仓|持有|定投)', content_lower): buy_sell['hold'].append(tweet)
        if re.search(r'(调仓|调整|暂停)', content_lower): buy_sell['adjust'].append(tweet)
    
    # Categories section
    report_lines.append("\n## 2. 分类整理\n按类别分组，相同基金/主题汇总。")
    for category, cat_tweets in categories.items():
        if cat_tweets:
            report_lines.append(f"\n### {category} ({len(cat_tweets)} posts)")
            for tweet in cat_tweets:
                content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
                report_lines.append(f"- **{tweet['fund_type']}**: {tweet['user']} ({tweet['time']}): {content_snippet} [链接]({tweet['link']})\n")
    
    # Fund types section
    report_lines.append("\n## 按基金类型分组")
    for fund_type, group_tweets in fund_groups.items():
        report_lines.append(f"\n### {fund_type} ({len(group_tweets)} posts)")
        for tweet in group_tweets:
            content_snippet = tweet['content'][:80] + '...' if len(tweet['content']) > 80 else tweet['content']
            report_lines.append(f"- {tweet['user']} ({tweet['time']}): {content_snippet} [链接]({tweet['link']})\n")
    
    # Buying/selling/holding/adjusting comparison
    report_lines.append("\n## 买卖/持仓/调仓对比")
    for action, action_tweets in buy_sell.items():
        if action_tweets:
            report_lines.append(f"\n### {action.capitalize()} ({len(action_tweets)} posts)")
            for tweet in action_tweets:
                content_snippet = tweet['content'][:60] + '...' if len(tweet['content']) > 60 else tweet['content']
                report_lines.append(f"- **{tweet['fund_type']}**: {tweet['user']}: {content_snippet} [链接]({tweet['link']})\n")
    
    # Key insights
    trends = []
    if buy_sell['buy']: trends.append("加仓热点：医疗/半导体基金（积极操作）")
    if buy_sell['sell'] or buy_sell['adjust']: trends.append("暂停或调仓新能源/光伏（回调风险）")
    if buy_sell['hold']: trends.append("强调长期定投，ETF/指数基金受关注")
    trends.append("政策驱动：关注央行支持、ETF获批等动态")
    
    report_lines.append(f"\n## 3. 关键洞察与趋势\n- **买卖/调仓建议**：{'; '.join(trends) if trends else '暂无明显趋势'}\n- **持仓概览**：长期定投为主，避免短期波动。\n- **建议**：使用基金诊断工具，关注政策变化。报告基于公开片段，如需实时，可优化脚本添加代理/Selenium。\n\n来源基于搜索，若需完整，可访问链接查看。")
    
    return ''.join(report_lines)

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
    report_content = generate_report(keyword, tweets)
    save_report(report_content)

if __name__ == "__main__":
    main()
