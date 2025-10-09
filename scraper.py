import asyncio
import os
from datetime import datetime
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# 频道/群组的用户名列表
CHANNEL_USERNAMES = [
    'FinanceNewsDaily', 
    'SubscriptionShare', 
    'clsvip', 
    'ywcqdz'
]

# 从 GitHub Secrets 获取 API ID 和 API Hash
API_ID = int(os.environ.get("TG_API_ID"))
API_HASH = os.environ.get("TG_API_HASH")

# 文件名将使用上海时间
SH_TZ = 'Asia/Shanghai'
now_shanghai = datetime.now().astimezone(datetime.fromtimestamp(0).astimezone(datetime.now().astimezone(None).tzinfo).tzinfo).replace(tzinfo=None) # 仅获取不带时区信息的datetime对象，配合workflow中的时区设置
# 格式化文件名，例如: 2025-10-09_12-30-00_telegram_content.md
FILENAME = now_shanghai.strftime("%Y-%m-%d_%H-%M-%S_telegram_content.md")

async def get_messages(client, entity):
    """异步获取指定频道的消息"""
    markdown_content = f"## 频道: @{entity.username}\n\n"
    print(f"开始抓取频道: @{entity.username}...")
    
    # 获取最近的 10 条消息 (可根据需要修改 limit)
    limit = 10
    
    try:
        async for message in client.iter_messages(entity, limit=limit):
            msg_text = ""
            # 消息发送时间 (格式化)
            post_time_sh = message.date.astimezone(datetime.fromtimestamp(0).astimezone(datetime.now().astimezone(None).tzinfo).tzinfo).strftime('%Y-%m-%d %H:%M:%S')
            
            msg_text += f"---\n**时间 (上海):** {post_time_sh} **(ID:** `{message.id}` **)**\n"
            
            # 文本内容
            if message.text:
                msg_text += f"\n{message.text}\n"

            # 媒体/文件信息 (仅列出，不下载)
            if message.media:
                media_type = "未知媒体"
                if isinstance(message.media, MessageMediaPhoto):
                    media_type = "图片"
                elif isinstance(message.media, MessageMediaDocument):
                    media_type = "文件/文档"
                
                # 提示用户手动查看原始链接
                if message.media.caption:
                     msg_text += f"\n*[{media_type}]* **[含标题]:** {message.media.caption}\n"
                else:
                    msg_text += f"\n*[{media_type}]*\n"
                
            # 原始消息链接
            if message.id:
                msg_text += f"\n**[原始链接](https://t.me/{entity.username}/{message.id})**\n"

            markdown_content += msg_text
            
        print(f"频道 @{entity.username} 抓取完成，共 {limit} 条消息。")
    
    except Exception as e:
        print(f"抓取 @{entity.username} 失败: {e}")
        markdown_content += f"\n**抓取失败:** {e}\n"

    return markdown_content

async def main():
    """主函数"""
    # session name 随便取, 在 GitHub Actions 上不需要存储会话文件
    async with TelegramClient('tg_scraper_session', API_ID, API_HASH) as client:
        
        all_content = f"# Telegram 频道内容抓取\n\n**抓取时间 (上海):** {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"
        
        for username in CHANNEL_USERNAMES:
            try:
                # 获取频道实体 (entity)
                entity = await client.get_entity(username)
                channel_content = await get_messages(client, entity)
                all_content += channel_content
            except Exception as e:
                error_msg = f"无法访问或获取实体 @{username}: {e}\n"
                print(error_msg)
                all_content += f"## 频道: @{username} (无法访问)\n\n**错误:** {e}\n\n"

        # 将所有内容写入 Markdown 文件
        with open(FILENAME, 'w', encoding='utf-8') as f:
            f.write(all_content)
            
        print(f"\n✅ 所有内容已成功保存到根目录的 **{FILENAME}** 文件中。")

if __name__ == '__main__':
    # Telethon 推荐使用 asyncio.run(main())
    asyncio.run(main())
