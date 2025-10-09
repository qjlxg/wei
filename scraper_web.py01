import os
import requests
import re
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 要抓取的频道列表 (使用 Web 预览链接格式: https://t.me/s/CHANNEL_USERNAME)
CHANNEL_USERNAMES = [
    'FinanceNewsDaily', 
    'SubscriptionShare', 
    'clsvip', 
    'ywcqdz',
    'ushas_analysis',
    'safe_trader_academy',
    'zh_technews', 
    'MacroFinanceHub',
    'GlobalMarketUpdates',
    'AshareDailyBrief'
]

# 设置上海时区
SH_TZ = pytz.timezone('Asia/Shanghai')
now_shanghai = datetime.now(SH_TZ)

# --- 路径和文件名生成逻辑 ---
# 1. 创建日期目录结构 (例如: 2025-10/09)
DATE_DIR = now_shanghai.strftime("%Y-%m/%d")

# 2. 完整保存路径 (例如: 2025-10/09/media)
BASE_DIR = os.path.join(os.getcwd(), DATE_DIR)
MEDIA_DIR = os.path.join(BASE_DIR, 'media')

# 3. 文件名 (例如: 14-30-00_telegram_web_content.md)
FILENAME_BASE = now_shanghai.strftime("%H-%M-%S_telegram_web_content.md")
FULL_FILENAME_PATH = os.path.join(BASE_DIR, FILENAME_BASE)
# --- 路径和文件名生成逻辑结束 ---

def setup_directories():
    """设置目录并清理旧的媒体文件"""
    # 确保主目录存在 (例如: 2025-10/09)
    os.makedirs(BASE_DIR, exist_ok=True)
    
    # 清理旧的媒体文件夹，确保每次运行都是全新的媒体文件
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
        # 设置 requests 重试机制
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
            clean_text = ""
            if text_tag:
                # 改进文本提取，减少截断风险
                clean_text = text_tag.get_text(separator='\n', strip=True)
                
            # 3. 提取并清理 Hashtag
            hashtags = re.findall(r'#\w+', clean_text)
            if hashtags:
                msg_text += "\n**标签**: " + ", ".join(hashtags) + "\n"
                clean_text = re.sub(r'#\w+', '', clean_text).strip()
            
            if clean_text:
                msg_text += f"\n{clean_text}\n"

            # 4. 媒体下载和标记
            media_tag = message.find('a', class_='tgme_widget_message_photo_wrap') or \
                        message.find('a', class_='tgme_widget_message_document_wrap')
            
            if media_tag and 'style' in media_tag.attrs:
                url_match = re.search(r'url\(["\']?(.*?)["\']?\)', media_tag['style'])
                
                if url_match and message_id != 'N/A':
                    media_url = url_match.group(1)
                    # 动态提取扩展名，默认为 .jpg
                    media_extension = os.path.splitext(media_url.split('?')[0])[1] or '.jpg'
                    
                    # 媒体文件相对路径，用于 Markdown 引用 (例如: media/FinanceNewsDaily_123.jpg)
                    media_filename_relative = os.path.join('media', f"{username}_{message_id}{media_extension}")
                    # 媒体文件绝对路径，用于文件写入
                    media_filename_full = os.path.join(BASE_DIR, media_filename_relative)

                    try:
                        media_response = session.get(media_url, timeout=10)
                        if media_response.status_code == 200:
                            with open(media_filename_full, 'wb') as f:
                                f.write(media_response.content)
                            # Markdown 链接使用 POSIX 风格路径 (/)
                            # 相对路径为：日期目录/media/文件名
                            md_path = os.path.join(DATE_DIR, media_filename_relative).replace(os.path.sep, '/')
                            msg_text += f"\n![媒体文件]({md_path})\n"
                            downloaded_count += 1
                        else:
                            msg_text += f"\n*[媒体文件下载失败: HTTP {media_response.status_code}]*\n"
                    except requests.exceptions.RequestException as download_err:
                        msg_text += f"\n*[媒体文件下载失败: {download_err}]*\n"
                elif media_tag:
                    msg_text += f"\n*[包含媒体/文件，请查看原始链接]({url})*\n"

            # 5. 跳过空消息（无文本且无媒体）
            if not clean_text and not media_tag:
                continue

            # 6. 原始消息链接
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

    # 7. 添加消息计数标题
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
