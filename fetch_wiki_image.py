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
# 必须设置 User-Agent，用于识别您的应用并避免 403 错误
HEADERS = {
    'User-Agent': 'GitHubActionWikiPotdScript/4.0 (contact: YourContact@example.com)'
}

# MIME 类型到文件扩展名的映射
MIME_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/svg+xml': '.svg',
    # 可以根据需要添加其他常见格式
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
    
    expand_data = data.get('expandtemplates', {})
    wikitext_node = expand_data.get('wikitext')
    
    wikitext = ''
    
    if isinstance(wikitext_node, dict):
        wikitext = wikitext_node.get('*', '').strip()
    elif isinstance(wikitext_node, str):
        wikitext = wikitext_node.strip()
        
    if not wikitext:
        raise ValueError(f"无法展开 POTD 模板 ({date_str})，可能是日期太靠前或当天无图片。")
        
    return wikitext

def get_image_details(filename):
    """
    第二步：获取图片文件的详细信息、URL 和 MIME 类型。
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size"
    }
    
    response = requests.get(API_ENDPOINT, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    
    pages = data.get('query', {}).get('pages', {})
    if not pages:
         raise ValueError(f"API 返回的查询结果中未找到页面信息。")

    page_id = next(iter(pages))
    page_info = pages[page_id]
    
    if page_id == '-1':
        raise ValueError(f"API 找不到文件: {filename}")
        
    image_info = page_info.get('imageinfo', [{}])[0]
    
    if not image_info:
        raise ValueError(f"无法获取文件详情: {filename}")
        
    caption_raw = image_info.get('extmetadata', {}).get('Caption', {}).get('value', 'N/A')
    caption = re.sub('<[^<]+?>', '', caption_raw)

    return {
        'title': page_info.get('title'),
        'url': image_info.get('url'),
        'mime': image_info.get('mime'),
        'caption': caption.strip()
    }

def download_image_file(url, mime_type, target_dir, timestamp_name):
    """
    下载图片文件并根据 MIME 类型确定后缀。
    """
    ext = MIME_TO_EXT.get(mime_type, '.bin')  # 默认使用 .bin 作为后缀，如果 MIME 类型未知
    
    file_path = os.path.join(target_dir, timestamp_name + ext)
    
    print(f"步骤 3/3: 正在下载图片到 {file_path}...")
    
    # 下载请求，使用 stream=True 以便处理大文件
    img_response = requests.get(url, stream=True, headers=HEADERS)
    img_response.raise_for_status()
    
    # 写入文件
    with open(file_path, 'wb') as f:
        for chunk in img_response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"✅ 图片文件下载并保存完成: {file_path}")
    return file_path


def fetch_and_save_wiki_picture():
    """
    获取维基媒体共享资源每日图片并保存。
    """
    try:
        # 1. 获取当前上海时间并格式化
        now_shanghai = datetime.now(SHANGHAI_TZ)
        date_str_potd = now_shanghai.strftime('%Y-%m-%d')
        
        # 2. 构造路径和文件基础名
        year = now_shanghai.strftime('%Y')
        month = now_shanghai.strftime('%m')
        timestamp_name = now_shanghai.strftime('%Y-%m-%d-%H-%M-%S')
        target_dir = os.path.join(year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        # 3. 获取文件名 (第一步 API)
        print(f"步骤 1/3: 正在获取 {date_str_potd} 的图片文件名...")
        filename = get_potd_filename(date_str_potd)
        print(f"找到文件名: {filename}")
        
        # 4. 获取图片详情 (第二步 API)
        print(f"步骤 2/3: 正在获取图片详情、URL 和 MIME 类型...")
        details = get_image_details(filename)
        
        # 5. 下载实际图片文件 (新步骤)
        download_path = download_image_file(
            url=details['url'],
            mime_type=details['mime'],
            target_dir=target_dir,
            timestamp_name=timestamp_name
        )
        
        # 6. (可选) 同时保存元数据文件 (仍推荐保留)
        metadata_file_path = os.path.join(target_dir, timestamp_name + '_meta.txt')
        result_content = (
            f"--- Wikimedia Commons Picture of the Day Metadata ---\n\n"
            f"File Name: {filename}\n"
            f"Image URL: {details['url']}\n"
            f"Local File: {os.path.basename(download_path)}\n"
            f"MIME Type: {details['mime']}\n"
            f"Caption: {details['caption']}\n"
        )
        with open(metadata_file_path, 'w', encoding='utf-8') as f:
            f.write(result_content)

        print(f"✅ 元数据保存完成: {metadata_file_path}")
        
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
