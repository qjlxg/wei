import os
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# 要抓取的频道列表 (使用 Web 预览链接格式: https://t.me/s/CHANNEL_USERNAME)
CHANNEL_USERNAMES = [
    'FinanceNewsDaily', 
    'SubscriptionShare', 
    'clsvip', 
    'ywcqdz'
]

# 设置上海时区
SH_TZ = pytz.timezone('Asia/Shanghai')
now_shanghai = datetime.now(SH_TZ)
# 格式化文件名，例如: 2025-10-09_11-55-20_telegram_web_content.md
FILENAME = now_shanghai.strftime("%Y-%m-%d_%H-%M-%S_telegram_web_content.md")

# 媒体文件将保存在 'media' 文件夹中
MEDIA_DIR = 'media'
os.makedirs(MEDIA_DIR, exist_ok=True)

def get_channel_content(username):
    """从 Telegram Web 预览页面抓取内容"""
    url = f"https://t.me/s/{username}"
    all_messages = []
    
    print(f"开始抓取 Web 预览页面: {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 寻找所有的消息容器
        messages = soup.find_all('div', class_='tgme_widget_message', limit=10) # 限制抓取最近10条消息
        
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
                # 将 <br> 标签替换为换行符
                text_content = str(text_tag).replace('<br/>', '\n').replace('<br>', '\n')
                clean_text = BeautifulSoup(text_content, 'html.parser').get_text(separator='\n').strip()
                
            # 3. 提取并清理 Hashtag
            hashtags = re.findall(r'#\w+', clean_text)
            if hashtags:
                msg_text += "\n**标签**: " + ", ".join(hashtags) + "\n"
                # 从文本中移除 hashtags
                clean_text = re.sub(r'#\w+', '', clean_text).strip()
            
            # 将清理后的文本添加到消息内容中
            if clean_text:
                msg_text += f"\n{clean_text}\n"

            # 4. 媒体下载和标记
            media_tag = message.find('a', class_='tgme_widget_message_photo_wrap') or \
                        message.find('a', class_='tgme_widget_message_document_wrap')
            
            if media_tag and 'style' in media_tag.attrs:
                # 尝试从 'style' 属性中提取图片 URL (仅对照片有效)
                url_match = re.search(r'url\(["\']?(.*?)["\']?\)', media_tag['style'])
                
                if url_match and message_id != 'N/A':
                    media_url = url_match.group(1)
                    media_extension = '.jpg' # 假设图片
                    
                    # 简化文件名，并保存到 media 文件夹
                    media_filename = os.path.join(MEDIA_DIR, f"{username}_{message_id}{media_extension}")
                    
                    try:
                        # 下载媒体文件
                        media_response = requests.get(media_url, timeout=10)
                        if media_response.status_code == 200:
                            with open(media_filename, 'wb') as f:
                                f.write(media_response.content)
                            # 在 Markdown 中嵌入图片链接
                            msg_text += f"\n![媒体文件]({media_filename.replace(os.path.sep, '/')})\n"
                        else:
                            msg_text += f"\n*[媒体文件下载失败: HTTP {media_response.status_code}]*\n"
                    except requests.exceptions.RequestException as download_err:
                        msg_text += f"\n*[媒体文件下载失败: {download_err}]*\n"
                elif media_tag:
                    # 如果不是图片或无法解析 URL，则仅提示
                    msg_text += f"\n*[包含媒体/文件，请查看原始链接] ({url})*\n"

            # 5. 原始消息链接
            if message_id != 'N/A':
                msg_text += f"\n**[原始链接](https://t.me/{username}/{message_id})**\n"
            
            all_messages.append(msg_text)
        
        print(f"频道 @{username} 抓取完成，共 {len(all_messages)} 条消息。")

    except requests.HTTPError as e:
        error_msg = f"HTTP 错误 (可能是 404 或 403): {e}. URL: {url}"
        print(error_msg)
        return f"## 频道: @{username}（共 0 条消息）\n\n**抓取失败 (HTTP 错误):** {e}\n"
    except Exception as e:
        error_msg = f"抓取 @{username} 失败: {e}"
        print(error_msg)
        return f"## 频道: @{username}（共 0 条消息）\n\n**抓取失败 (未知错误):** {e}\n"

    # 6. 添加消息计数标题
    header = f"## 频道: @{username}（共 {len(all_messages)} 条消息）\n\n"
    return header + "\n".join(all_messages)


def main():
    """主函数"""
    # 移除旧的媒体文件夹，确保每次运行都是全新的媒体文件
    if os.path.exists(MEDIA_DIR):
        import shutil
        shutil.rmtree(MEDIA_DIR)
        os.makedirs(MEDIA_DIR, exist_ok=True)
        
    all_content = f"# Telegram 频道内容抓取 (Web 预览)\n\n**抓取时间 (上海):** {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
    
    for username in CHANNEL_USERNAMES:
        channel_content = get_channel_content(username)
        all_content += channel_content

    # 将所有内容写入 Markdown 文件
    with open(FILENAME, 'w', encoding='utf-8') as f:
        f.write(all_content)
        
    print(f"\n✅ 所有内容已成功保存到根目录的 **{FILENAME}** 文件中。")
    print(f"媒体文件保存到 **{MEDIA_DIR}** 文件夹中。")

if __name__ == '__main__':
    main()
