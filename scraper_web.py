import os
import requests
import re
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from requests.adapters import HTTPAdapter
# 注意：这里我们使用 requests.packages 兼容旧版本，
# 建议同时在 requirements.txt 中包含 urllib3
from requests.packages.urllib3.util.retry import Retry 
import json

# =========================================================
# 【配置区】要抓取的频道列表
# =========================================================
CHANNEL_USERNAMES = [
    # 现有核心金融频道
    'FinanceNewsDaily', 
    'SubscriptionShare', 
    'clsvip', 
    'ywcqdz',
    # 新增的分析与科技频道
    'ushas_analysis',
    'safe_trader_academy',
    'zh_technews', 
    'MacroFinanceHub',
    'GlobalMarketUpdates',
    'AshareDailyBrief'
]
# =========================================================
# =========================================================


# 设置上海时区
SH_TZ = pytz.timezone('Asia/Shanghai')
now_shanghai = datetime.now(SH_TZ)

# --- 路径和文件名生成逻辑 ---
# 1. 创建日期目录结构 (例如: 2025-10/09)
DATE_DIR = now_shanghai.strftime("%Y-%m/%d")

# 2. 完整保存路径 (例如: 2025-10/09/media)
BASE_DIR = os.path.join(os.getcwd(), DATE_DIR)
MEDIA_DIR = os.path.join(BASE_DIR, 'media')

# 3. 文件名 (例如: 15-20-00_telegram_web_content.md)
FILENAME_BASE = now_shanghai.strftime("%H-%M-%S_telegram_web_content.md")
FULL_FILENAME_PATH = os.path.join(BASE_DIR, FILENAME_BASE)
# --- 路径和文件名生成逻辑结束 ---

# --- 市场影响分析配置 ---
IMPACT_KEYWORDS = {
    # 积极关键词 (分数 +2)
    'positive': ['涨', '上涨', '大涨', '飙涨', '突破', '利好', '新高', '看好', '增持', '走强', '复苏', '站上', '扩大', '利多', '领先'],
    # 消极关键词 (分数 -2)
    'negative': ['跌', '下跌', '大跌', '走低', '利空', '下行', '风险', '担忧', '疲软', '收窄', '走弱', '缩减', '亏损', '做空'],
    # 中性/关注关键词 (分数 +1 或 -1)
    'neutral_positive': ['回升', '反弹', '温和', '企稳', '放量', '回购'],
    'neutral_negative': ['压力', '放缓', '震荡', '回调', '盘整', '高位'],
}

SECTOR_KEYWORDS = {
    '黄金/贵金属': ['黄金', '沪金', '白银', '钯金', '金价', '贵金属'],
    'A股/大盘': ['A股', '沪指', '深成指', '创业板', '沪深', '市场', '京三市', '北向资金'],
    '期货/大宗商品': ['期货', '棕榈油', '生猪', '鸡蛋', 'LPG', '集运', '液化天然气', '碳酸锂', '铜价', '原油', '大宗商品', '工业品'],
    '科技/半导体': ['芯片', '科创50', '中芯国际', '华虹公司', '先进封装', '内存', 'SSD', 'AI', '大模型', '算力', '半导体'],
    '新能源/储能': ['碳酸锂', '储能', '光伏', '电池级', 'HVDC', '新能源汽车', '风电'],
    '宏观/央行': ['美联储', '央行', '降息', '加息', '逆回购', 'SHIBOR', '政府预算', '美国国债', '关税', '通胀', 'GDP', 'PMI'],
    '港股/汇率': ['恒生指数', '恒指', '泰铢', '美元', '卢比', '新加坡元', '汇率', '港股', '离岸人民币'],
    '稀土': ['稀土', '出口管制'],
    '数字货币': ['比特币', '以太坊', 'BTC', 'ETH', '加密货币', '区块链'],
}


def analyze_market_impact(text, hashtags):
    """
    基于关键词和标签对文本进行基本的市场影响分析。
    返回一个包含影响、行业和情绪的字典。
    """
    score = 0
    impact_sectors = set()
    
    # 1. 识别行业/资产 (基于文本和标签)
    combined_content = text + " ".join(hashtags)
    for sector, keywords in SECTOR_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined_content:
                impact_sectors.add(sector)
                break
    
    # 2. 计算情绪分数
    for word in IMPACT_KEYWORDS['positive']:
        score += combined_content.count(word) * 2
    for word in IMPACT_KEYWORDS['neutral_positive']:
        score += combined_content.count(word) * 1
        
    for word in IMPACT_KEYWORDS['negative']:
        score -= combined_content.count(word) * 2
    for word in IMPACT_KEYWORDS['neutral_negative']:
        score -= combined_content.count(word) * 1

    # 3. 确定最终影响标签
    if score >= 3:
        impact_label = "显著利好 (Bullish)"
        impact_color = "🟢"
    elif score >= 1:
        impact_label = "潜在利好 (Positive)"
        impact_color = "🟡"
    elif score <= -3:
        impact_label = "显著利空 (Bearish)"
        impact_color = "🔴"
    elif score <= -1:
        impact_label = "潜在利空 (Negative)"
        impact_color = "🟠"
    else:
        impact_label = "中性/需关注 (Neutral)"
        impact_color = "⚪"
        
    # 4. 格式化输出
    if not impact_sectors:
        sector_str = "未识别行业"
    else:
        sector_str = "、".join(list(impact_sectors))

    summary = f"**市场影响** {impact_color} **{impact_label}**"
    if impact_sectors:
        summary += f" - 关注板块：{sector_str}"
        
    return summary

# --- 实用工具函数 ---

def setup_directories():
    """设置目录并清理旧的媒体文件"""
    # 确保主目录存在 (例如: 2025-10/09)
    os.makedirs(BASE_DIR, exist_ok=True)
    
    # 清理旧的媒体文件夹，确保每次运行都是全新的媒体文件
    # 这里的清理只针对当前运行创建的媒体文件夹，防止提交时包含上一次运行的媒体文件
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
        # 设置 requests 重试机制，增强抓取稳定性
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        response = session.get(url, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 寻找所有的消息容器
        messages = soup.find_all('div', class_='tgme_widget_message', limit=10)
        
        if not messages:
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
            
            # 2. 提取并清理消息文本内容
            text_tag = message.find('div', class_='tgme_widget_message_text')
            if text_tag:
                # 改进文本提取，将 <br> 视为换行符，并移除空格
                clean_text = text_tag.get_text(separator='\n', strip=True)
                
            # 3. 提取并清理 Hashtag
            hashtags = re.findall(r'#\w+', clean_text)
            if hashtags:
                msg_text += "\n**标签**: " + ", ".join(hashtags) + "\n"
                # 从文本中移除 hashtags
                clean_text = re.sub(r'#\w+', '', clean_text).strip()
            
            # 4. 媒体下载和标记
            media_tag = message.find('a', class_='tgme_widget_message_photo_wrap') or \
                        message.find('a', class_='tgme_widget_message_document_wrap')
            
            if media_tag and 'style' in media_tag.attrs:
                url_match = re.search(r'url\(["\']?(.*?)["\']?\)', media_tag['style'])
                
                if url_match and message_id != 'N/A':
                    media_url = url_match.group(1)
                    # 动态提取扩展名
                    media_extension = os.path.splitext(media_url.split('?')[0])[1] or '.jpg'
                    
                    media_filename_relative = os.path.join('media', f"{username}_{message_id}{media_extension}")
                    media_filename_full = os.path.join(BASE_DIR, media_filename_relative)

                    try:
                        media_response = session.get(media_url, timeout=10)
                        if media_response.status_code == 200:
                            with open(media_filename_full, 'wb') as f:
                                f.write(media_response.content)
                            # Markdown 链接使用 POSIX 风格路径 (/)
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
            
            # 6. 跳过空消息（无文本且无媒体）
            if not clean_text and not media_tag:
                continue

            # 7. 添加清理后的文本和分析结果
            if clean_text:
                msg_text += f"\n{clean_text}\n"

            # 8. 添加分析结果
            msg_text += f"\n{impact_summary}\n"
            
            # 9. 原始消息链接
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

    # 10. 添加消息计数标题
    header = f"## 频道: @{username}（共 {len(all_messages)} 条消息）\n\n"
    return header + "\n".join(all_messages)

def main():
    """主函数"""
    setup_directories() # 创建并清理目录

    all_content = f"# Telegram 频道内容抓取 (Web 预览)\n\n**抓取时间 (上海):** {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
    
    for username in CHANNEL_USERNAMES:
        channel_content = get_channel_content(username)
        all_content += channel_content

    # 将所有内容写入 Markdown 文件
    with open(FULL_FILENAME_PATH, 'w', encoding='utf-8') as f:
        f.write(all_content)
        
    print(f"\n✅ 所有内容已成功保存到 **{FULL_FILENAME_PATH}** 文件中。")

if __name__ == '__main__':
    main()
