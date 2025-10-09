import os
import requests
import re
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry 
import json
from collections import Counter

# =========================================================
# 【配置区】要抓取的频道列表
# =========================================================
CHANNEL_USERNAMES = [
    # 现有核心金融频道
    'FinanceNewsDaily', 
    'SubscriptionShare', 
    'clsvip', 
    'ywcqdz',
    # 验证有效/修正的新增频道 (去除 0 消息)
    'ushasanalysis',       # 修正 ushas_analysis
    'thesafetraderacademy', # 替换 safe_trader_academy
    'TechNewsTodayBot',    # 替换 zh_technews
    'MacroHub',            # 替换 MacroFinanceHub
    'GlobalMarketUpdates', # 保留
    'ChineseStockMarket',  # 替换 AshareDailyBrief
    'NiftyProX',           # 修正 niftyprox
    'equity99',
    'learn2tradenews',     # 修正 learn2trade
    'TechNews',            # 替换 TechNews2024
    'GlobalMacro',         # 替换 GlobalMacroReport
    'CommoditySignals',    # 替换 CommodityTradeInfo
    'tfainvestments',      # 替换 FinancialAnalystView
    'CryptoMarketUpdates',
    # 新增验证活跃的中文美股频道 (2025 年活跃)
    'BloombergZh',         # 彭博中文美股新闻
    'meigucaijing',        # 美股财经
    'usstocknews',         # 美股新闻
    'xueqiushare',         # 雪球美股
    'sinafinance',         # 新浪美股
    'caijingmeigu'         # 财经美股
]
# =========================================================
# =========================================================

# 设置上海时区
SH_TZ = pytz.timezone('Asia/Shanghai')
now_shanghai = datetime.now(SH_TZ)

# --- 路径和文件名生成逻辑 ---
DATE_DIR = now_shanghai.strftime("%Y-%m/%d")
BASE_DIR = os.path.join(os.getcwd(), DATE_DIR)
MEDIA_DIR = os.path.join(BASE_DIR, 'media')
FILENAME_BASE = now_shanghai.strftime("%H-%M-%S_telegram_web_content.md")
FULL_FILENAME_PATH = os.path.join(BASE_DIR, FILENAME_BASE)

# --- 市场影响分析配置 ---
IMPACT_KEYWORDS = {
    'positive': ['涨', '上涨', '大涨', '飙涨', '暴涨', '突破', '利好', '新高', '看好', '增持', '走强', '复苏', '站上', '扩大', '利多', '领先'],
    'negative': ['跌', '下跌', '大跌', '暴跌', '走低', '利空', '下行', '风险', '担忧', '疲软', '收窄', '走弱', '缩减', '亏损', '做空'],
    'neutral_positive': ['回升', '反弹', '温和', '企稳', '放量', '回购'],
    'neutral_negative': ['压力', '放缓', '震荡', '回调', '盘整', '高位'],
}

SECTOR_KEYWORDS = {
    '黄金/贵金属': ['黄金', '沪金', '白银', '钯金', '金价', '贵金属', 'XAUUSD'],
    'A股/大盘': ['A股', '沪指', '深成指', '创业板', '沪深', '市场', '京三市', '北向资金', 'Nifty'],
    '期货/大宗商品': ['期货', '棕榈油', '生猪', '鸡蛋', 'LPG', '集运', '液化天然气', '碳酸锂', '铜价', '原油', '大宗商品', '工业品'],
    '科技/半导体': ['芯片', '科创50', '中芯国际', '华虹公司', '先进封装', '内存', 'SSD', 'AI', '大模型', '算力', '半导体'],
    '新能源/储能': ['碳酸锂', '储能', '光伏', '电池级', 'HVDC', '新能源汽车', '风电'],
    '宏观/央行': ['美联储', '央行', '降息', '加息', '逆回购', 'SHIBOR', '政府预算', '美国国债', '关税', '通胀', 'GDP', 'PMI'],
    '港股/汇率': ['恒生指数', '恒指', '泰铢', '美元', '卢比', '新加坡元', '汇率', '港股', '离岸人民币'],
    '稀土': ['稀土', '出口管制'],
    '数字货币': ['比特币', '以太坊', 'BTC', 'ETH', '加密货币', '区块链', 'Solana'],
    '指数/银行': ['Bank Nifty', 'Nifty', '指数', '银行股'],
    '全球/外汇': ['外汇', 'USD', 'EUR', 'GBP', '全球市场'],
    '基金/ETF': ['ETF', '基金', '黄金ETF', '有色ETF', '指数基金', '避险基金'],
    '期权/交易信号': ['期权', '信号', '做多', '做空', '看涨', '看跌', '合约'],
    '美股': ['美股', 'NASDAQ', 'S&P', 'Dow', 'US30', 'AMD', 'NVDA', 'AAPL', 'Dow Jones', 'S&P 500']
}

def analyze_market_impact(text, hashtags):
    score = 0
    impact_sectors = set()
    stocks = []
    
    # 提取股票代码（扩展美股/A 股模式）
    stock_pattern = r'(中芯国际|华虹公司|江波龙|芯联集成|中微公司|西部超导|芯原股份|汇丰控股|英伟达|NVDA|AAPL|AMD|TSLA|GOOGL|MSFT)'
    stocks = re.findall(stock_pattern, text)
    
    combined_content = text + " ".join(hashtags)
    for sector, keywords in SECTOR_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined_content:
                impact_sectors.add(sector)
                break
    
    # 计算分数（优化权重，如 '暴涨' +3）
    for word in IMPACT_KEYWORDS['positive']:
        score += combined_content.count(word) * (3 if word in ['暴涨', '飙涨'] else 2)
    for word in IMPACT_KEYWORDS['neutral_positive']:
        score += combined_content.count(word) * 1
    for word in IMPACT_KEYWORDS['negative']:
        score -= combined_content.count(word) * (3 if word in ['暴跌', '大跌'] else 2)
    for word in IMPACT_KEYWORDS['neutral_negative']:
        score -= combined_content.count(word) * 1

    # 确定标签
    if score >= 4:
        impact_label = "显著利好 (Bullish)"
        impact_color = "🟢"
    elif score >= 1:
        impact_label = "潜在利好 (Positive)"
        impact_color = "🟡"
    elif score <= -4:
        impact_label = "显著利空 (Bearish)"
        impact_color = "🔴"
    elif score <= -1:
        impact_label = "潜在利空 (Negative)"
        impact_color = "🟠"
    else:
        impact_label = "中性/需关注 (Neutral)"
        impact_color = "⚪"
        
    sector_str = "、".join(impact_sectors) if impact_sectors else "未识别行业"
    summary = f"**市场影响** {impact_color} **{impact_label}** - 关注板块：{sector_str}"
    if stocks:
        summary += f"\n**提及股票**：{', '.join(set(stocks))}"
        
    return summary

# --- 实用工具函数 ---

def setup_directories():
    os.makedirs(BASE_DIR, exist_ok=True)
    if os.path.exists(MEDIA_DIR):
        shutil.rmtree(MEDIA_DIR)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    print(f"数据将保存到目录: {BASE_DIR}")

def get_channel_content(username):
    """从 Telegram Web 预览页面抓取内容"""
    url = f"https://t.me/s/{username}"
    all_messages = []
    downloaded_count = 0
    
    print(f"开始抓取 Web 预览页面: {url}...")
    
    try:
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        response = session.get(url, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 优化文本提取：从 soup 直接获取完整消息
        messages = soup.find_all('div', class_='tgme_widget_message', limit=5)  # 优化 limit=5 减少负载
        
        if not messages:
            print(f"频道 @{username} 无消息，跳过分析。")
            return f"## 频道: @{username}（共 0 条消息）\n\n**警告:** 未找到任何消息，该频道可能不存在或启用了内容限制。\n"

        for message in messages:
            msg_text = ""
            message_id = 'N/A'
            clean_text = ""
            hashtags = []
            media_tag = None
            
            # 1. 获取消息ID和时间戳
            link_tag = message.find('a', class_='tgme_widget_message_date')
            if link_tag and 'href' in link_tag.attrs:
                parts = link_tag['href'].split('/')
                message_id = parts[-1] if parts[-1].isdigit() else 'N/A'
                
                time_tag = link_tag.find('time')
                if time_tag and 'datetime' in time_tag.attrs:
                    time_utc = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                    time_sh = time_utc.astimezone(SH_TZ).strftime('%Y-%m-%d %H:%M:%S')
                    
                    msg_text += f"---\n**时间 (上海):** {time_sh} **(ID:** `{message_id}` **)**\n"
            
            # 2. 提取并清理消息文本内容（优化避免截断）
            text_tag = message.find('div', class_='tgme_widget_message_text')
            if text_tag:
                # 使用 str(text_tag).replace 完整提取
                text_content = str(text_tag).replace('<br/>', '\n').replace('<br>', '\n')
                clean_text = BeautifulSoup(text_content, 'html.parser').get_text(separator='\n', strip=True)
                
            # 3. 提取并清理 Hashtag
            hashtags = re.findall(r'#\w+', clean_text)
            if hashtags:
                msg_text += "\n**标签**: " + ", ".join(hashtags) + "\n"
                clean_text = re.sub(r'#\w+', '', clean_text).strip()
            
            # 4. 媒体下载和标记
            media_tag = message.find('a', class_='tgme_widget_message_photo_wrap') or \
                        message.find('a', class_='tgme_widget_message_document_wrap')
            
            if media_tag and 'style' in media_tag.attrs:
                url_match = re.search(r'url\(["\']?(.*?)["\']?\)', media_tag['style'])
                
                if url_match and message_id != 'N/A':
                    media_url = url_match.group(1)
                    media_extension = os.path.splitext(media_url.split('?')[0])[1] or '.jpg'
                    media_filename_relative = os.path.join('media', f"{username}_{message_id}{media_extension}")
                    media_filename_full = os.path.join(BASE_DIR, media_filename_relative)

                    try:
                        media_response = session.get(media_url, timeout=10)
                        if media_response.status_code == 200:
                            with open(media_filename_full, 'wb') as f:
                                f.write(media_response.content)
                            md_path = os.path.join(DATE_DIR, media_filename_relative).replace(os.path.sep, '/')
                            msg_text += f"\n![媒体文件]({md_path})\n"
                            downloaded_count += 1
                        else:
                            msg_text += f"\n*[媒体文件下载失败: HTTP {media_response.status_code}]*\n"
                    except requests.exceptions.RequestException as download_err:
                        msg_text += f"\n*[媒体文件下载失败: {download_err}]*\n"
                elif media_tag:
                    msg_text += f"\n*[包含媒体/文件，请查看原始链接]({url})*\n"

            # 5. 市场影响分析
            impact_summary = analyze_market_impact(clean_text, hashtags)
            
            # 6. 跳过空消息
            if not clean_text and not media_tag:
                continue

            # 7. 添加清理后的文本和分析结果
            if clean_text:
                msg_text += f"\n{clean_text}\n"
            msg_text += f"\n{impact_summary}\n"
            
            # 8. 原始消息链接
            if message_id != 'N/A':
                msg_text += f"\n**[原始链接](https://t.me/{username}/{message_id})**\n"
            
            all_messages.append(msg_text)
        
        print(f"频道 @{username} 抓取完成，共 {len(all_messages)} 条消息，下载媒体: {downloaded_count} 个。")

    except requests.HTTPError as e:
        error_msg = f"HTTP 错误 (可能是 404 或 403): {e}. URL: {url}"
        print(error_msg)
        return f"## 频道: @{username}（共 0 条消息）\n\n**抓取失败 (HTTP 错误):** {e}\n"
    except Exception as e:
        error_msg = f"抓取 @{username} 失败: {e}"
        print(error_msg)
        return f"## 频道: @{username}（共 0 条消息）\n\n**抓取失败 (未知错误):** {e}\n"

    header = f"## 频道: @{username}（共 {len(all_messages)} 条消息）\n\n"
    return header + "\n".join(all_messages)

def generate_overall_summary(all_content):
    """生成整体影响总结 JSON"""
    impacts = re.findall(r'\*\*市场影响\*\* (🟢|🟡|🟠|🔴|⚪) \*\*(.+?)\*\*', all_content, re.DOTALL)
    sector_mentions = re.findall(r'关注板块：(.+?)(?=\n|$)', all_content)
    stocks = re.findall(r'\*\*提及股票\*\*：(.+?)(?=\n|$)', all_content)
    
    impact_counter = Counter([label for _, label in impacts])
    emoji_to_label = {'🟢': 'Bullish', '🟡': 'Positive', '🟠': 'Negative', '🔴': 'Bearish', '⚪': 'Neutral'}
    
    summary = {
        'timestamp': now_shanghai.strftime('%Y-%m-%d %H:%M:%S'),
        'total_messages': len(re.findall(r'---\n\*\*时间', all_content)),
        'impact_distribution': {emoji_to_label[emoji]: count for emoji, count in impact_counter.items() if emoji in emoji_to_label},
        'top_sectors': Counter(sector_mentions).most_common(5),
        'top_stocks': Counter([stock for stocks_list in stocks for stock in stocks_list.split(', ')]).most_common(5),
        'recommendation': '整体利好美股/科技/黄金板块，警惕港股/稀土风险' if impact_counter['🟢'] > impact_counter['🔴'] else '中性市场，观察宏观/美股信号'
    }
    
    json_path = FULL_FILENAME_PATH.replace('.md', '_overall_summary.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 整体总结已保存到 **{json_path}**")

def main():
    """主函数"""
    setup_directories()
    all_content = f"# Telegram 频道内容抓取 (Web 预览)\n\n**抓取时间 (上海):** {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
    
    for username in CHANNEL_USERNAMES:
        channel_content = get_channel_content(username)
        all_content += channel_content

    with open(FULL_FILENAME_PATH, 'w', encoding='utf-8') as f:
        f.write(all_content)
        
    print(f"\n✅ 所有内容已成功保存到 **{FULL_FILENAME_PATH}** 文件中。")
    
    generate_overall_summary(all_content)

if __name__ == '__main__':
    main()
