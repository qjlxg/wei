import os
import requests
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
# 格式化文件名，例如: 2025-10-09_12-30-00_telegram_web_content.md
FILENAME = now_shanghai.strftime("%Y-%m-%d_%H-%M-%S_telegram_web_content.md")

def get_channel_content(username):
    """从 Telegram Web 预览页面抓取内容"""
    url = f"https://t.me/s/{username}"
    markdown_content = f"## 频道: @{username}\n\n"
    print(f"开始抓取 Web 预览页面: {url}...")
    
    try:
        # 发送请求
        response = requests.get(url)
        response.raise_for_status() # 检查请求是否成功
        
        # 使用 BeautifulSoup 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 寻找所有的消息容器（Telegram Web 预览中通常是 'tgme_widget_message' 类）
        messages = soup.find_all('div', class_='tgme_widget_message', limit=10) # 限制抓取最近10条消息
        
        if not messages:
            markdown_content += "**警告:** 未找到任何消息，该频道可能不存在或启用了内容限制。\n"
            return markdown_content

        for message in messages:
            msg_text = ""
            
            # 消息ID和时间戳
            link_tag = message.find('a', class_='tgme_widget_message_date')
            if link_tag and 'href' in link_tag.attrs:
                # 提取消息ID
                parts = link_tag['href'].split('/')
                message_id = parts[-1] if parts[-1].isdigit() else 'N/A'
                
                # 提取时间 (Web 预览页面的时间是UTC)
                time_tag = link_tag.find('time')
                if time_tag and 'datetime' in time_tag.attrs:
                    time_utc = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                    # 转换为上海时间
                    time_sh = time_utc.astimezone(SH_TZ).strftime('%Y-%m-%d %H:%M:%S')
                    
                    msg_text += f"---\n**时间 (上海):** {time_sh} **(ID:** `{message_id}` **)**\n"
            
            # 提取消息文本内容
            text_tag = message.find('div', class_='tgme_widget_message_text')
            if text_tag:
                # 将 <br> 标签替换为换行符，并移除其他标签
                text_content = str(text_tag).replace('<br/>', '\n').replace('<br>', '\n')
                clean_text = BeautifulSoup(text_content, 'html.parser').get_text(separator='\n')
                msg_text += f"\n{clean_text.strip()}\n"

            # 媒体/文件信息 (仅提示)
            media_tag = message.find('a', class_='tgme_widget_message_photo_wrap') or \
                        message.find('div', class_='tgme_widget_message_document')
            if media_tag:
                msg_text += f"\n*[包含媒体/文件，请查看](https://t.me/{username}/{message_id})*\n"

            # 原始消息链接
            if message_id != 'N/A':
                msg_text += f"\n**[原始链接](https://t.me/{username}/{message_id})**\n"
            
            markdown_content += msg_text
            
        print(f"频道 @{username} 抓取完成，共 {len(messages)} 条消息。")
        
    except requests.HTTPError as e:
        error_msg = f"HTTP 错误 (可能是 404 或 403): {e}. URL: {url}"
        print(error_msg)
        markdown_content += f"\n**抓取失败 (HTTP 错误):** {e}\n"
    except Exception as e:
        error_msg = f"抓取 @{username} 失败: {e}"
        print(error_msg)
        markdown_content += f"\n**抓取失败 (未知错误):** {e}\n"

    return markdown_content

def main():
    """主函数"""
    all_content = f"# Telegram 频道内容抓取 (Web 预览)\n\n**抓取时间 (上海):** {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
    
    for username in CHANNEL_USERNAMES:
        channel_content = get_channel_content(username)
        all_content += channel_content

    # 将所有内容写入 Markdown 文件
    with open(FILENAME, 'w', encoding='utf-8') as f:
        f.write(all_content)
        
    print(f"\n✅ 所有内容已成功保存到根目录的 **{FILENAME}** 文件中。")

if __name__ == '__main__':
    main()
