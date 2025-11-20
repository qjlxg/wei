import requests
from datetime import datetime
import pytz
import json
import os
import re

# 设置时区为上海
SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')
# 维基共享资源 API
API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
# 必须设置 User-Agent，避免 403 问题的关键，请替换为您的联系方式
HEADERS = {
    'User-Agent': 'GitHubActionScript/2.0 (contact: your-email@example.com)'
}

def get_potd_filename(date_str):
    """
    第一步：通过展开 POTD 模板获取当天的图片文件名 (来自 Wikimedia Commons)。
    """
    template_text = f"{{{{Potd/{date_str}}}}}"
    params = {
        "action": "expandtemplates",
        "format": "json",
        "prop": "wikitext",
        "text": template_text
    }
    
    response = requests.get(API_ENDPOINT, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    # 展开模板的结果通常直接是图片文件名
    wikitext = data.get('expandtemplates', {}).get('wikitext', {}).get('*', '').strip()
    
    if not wikitext:
        # 如果是未来日期（如您测试的 2025-11-20），模板可能为空
        raise ValueError("无法展开 POTD 模板，可能是日期太靠前，或当天无图片。")
        
    return wikitext

def get_image_details(filename):
    """
    第二步：获取图片文件的详细信息和 URL。
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size" # 获取 URL, 元数据, MIME 类型, 大小
    }
    
    response = requests.get(API_ENDPOINT, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    # 解析页面ID
    page_id = next(iter(data.get('query', {}).get('pages', {})))
    page_info = data['query']['pages'][page_id]
    
    if page_id == '-1':
        raise ValueError(f"无法找到文件: {filename}")
        
    image_info = page_info.get('imageinfo', [{}])[0]
    
    if not image_info:
        raise ValueError(f"无法获取文件详情: {filename}")
        
    # 提取 Caption，并尝试去除 HTML 标签，使其更易读
    caption_raw = image_info.get('extmetadata', {}).get('Caption', {}).get('value', 'N/A')
    caption = re.sub('<[^<]+?>', '', caption_raw)

    return {
        'title': page_info.get('title'),
        'url': image_info.get('url'),
        'mime': image_info.get('mime'),
        'caption': caption.strip()
    }


def fetch_and_save_wiki_picture():
    """
    获取维基媒体共享资源每日图片并保存。
    """
    try:
        # 1. 获取当前上海时间并格式化
        now_shanghai = datetime.now(SHANGHAI_TZ)
        date_str_potd = now_shanghai.strftime('%Y-%m-%d')
        
        # 2. 获取文件名 (第一步 API)
        print(f"步骤 1/2: 正在获取 {date_str_potd} 的图片文件名...")
        filename = get_potd_filename(date_str_potd)
        print(f"找到文件名: {filename}")
        
        # 3. 获取图片详情 (第二步 API)
        print(f"步骤 2/2: 正在获取图片详情和 URL...")
        details = get_image_details(filename)
        
        # 4. 格式化输出内容
        result_content = (
            f"--- Wikimedia Commons Picture of the Day for {date_str_potd} ---\n\n"
            f"File Name: {filename}\n"
            f"Full Page Title: {details['title']}\n"
            f"Image URL: {details['url']}\n"
            f"MIME Type: {details['mime']}\n"
            f"Caption (Simplified): {details['caption']}\n"
        )
        
        # 5. 构造文件名和路径 (保持与您的要求一致)
        year = now_shanghai.strftime('%Y')
        month = now_shanghai.strftime('%m')
        timestamp_filename = now_shanghai.strftime('%Y-%m-%d-%H-%M-%S') + '.txt'
        
        # 目标目录: YYYY/MM
        target_dir = os.path.join(year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        # 目标文件路径
        file_path = os.path.join(target_dir, timestamp_filename)
        
        # 6. 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result_content)
        
        print(f"✅ 成功获取维基图片信息并保存到: {file_path}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 发生网络请求错误: {e}")
        if e.response is not None:
             print(f"HTTP 状态码: {e.response.status_code}")
        exit(1)
    except ValueError as e:
        print(f"❌ 数据解析或查找错误: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 发生其他错误: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_save_wiki_picture()
