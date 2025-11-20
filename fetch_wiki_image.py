import requests
from datetime import datetime
import pytz
import json
import os

# 设置时区为上海
SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')

def fetch_and_save_wiki_picture():
    """
    使用 Wikimedia REST API 获取维基百科每日图片并保存。
    """
    # 1. 获取当前上海时间并格式化
    now_shanghai = datetime.now(SHANGHAI_TZ)
    # REST API 使用 YYYY/MM/DD 格式
    date_path = now_shanghai.strftime('%Y/%m/%d')
    timestamp_filename = now_shanghai.strftime('%Y-%m-%d-%H-%M-%S') + '.txt'
    
    # 2. 构造 Wikimedia REST API URL
    # 这个 API 专门用于获取某一天的精选内容（包括每日图片）
    API_URL = f"https://en.wikipedia.org/api/rest_v1/feed/featured/{date_path}"
    
    # 3. 设置 User-Agent 头部 (解决 403 问题的关键)
    # 请将 YourName/YourAppVersion 替换为您的应用名称和版本，并提供一个联系邮箱
    headers = {
        'User-Agent': 'YourGitHubActionScript/1.0 (contact: your-email@example.com)'
    }

    print(f"尝试从 {API_URL} 获取数据...")
    
    try:
        # 发送请求
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status() # 如果状态码是 4xx 或 5xx，将抛出异常

        data = response.json()

        # 从响应中提取每日图片 (Picture of the Day) 部分
        potd_data = data.get('tfa') # 通常 Daily Featured Article 在 tfa，每日图片在 potd，但 Featured Feed 结构会变化
        
        # 更好的方法是直接寻找 'onthisday' 或 'potd'
        potd_data = data.get('potd')
        if not potd_data:
            raise ValueError("API响应中未找到每日图片 (POTD) 数据。")

        # 提取关键信息
        image_title = potd_data.get('title', 'N/A')
        image_url = potd_data.get('originalimage', {}).get('source', 'N/A')
        image_caption = potd_data.get('caption', {}).get('text', 'N/A')
        
        # 格式化输出内容
        result_content = (
            f"--- Wikipedia Picture of the Day for {date_path.replace('/', '-')} ---\n\n"
            f"Image Title: {image_title}\n"
            f"Image URL: {image_url}\n"
            f"Caption: {image_caption}\n\n"
            f"Raw Data:\n{json.dumps(potd_data, indent=2, ensure_ascii=False)}"
        )
        
        # 4. 构造文件名和路径
        year = now_shanghai.strftime('%Y')
        month = now_shanghai.strftime('%m')
        
        # 目标目录: YYYY/MM
        target_dir = os.path.join(year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        # 目标文件路径
        file_path = os.path.join(target_dir, timestamp_filename)
        
        # 5. 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result_content)
        
        print(f"✅ 成功获取维基图片信息并保存到: {file_path}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 发生网络请求错误: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 发生其他错误: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_save_wiki_picture()
