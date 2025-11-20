import requests
from datetime import datetime, timedelta
import pytz
import json
import os
import re

# --- 配置 ---
# 设置时区为上海
SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')
# 维基共享资源 API
API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
# 必须设置 User-Agent，请替换为您的联系邮箱
HEADERS = {
    'User-Agent': 'GitHubActionWikiPotdBatchDownloader/5.0 (contact: YourContact@example.com)'
}
# 存储图片的根目录
BASE_DOWNLOAD_DIR = 'wiki_image'
# 开始批量下载的年份（可以根据需要调整）
START_YEAR = 2024

# MIME 类型到文件扩展名的映射
MIME_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/svg+xml': '.svg',
    # 添加其他格式...
    'application/octet-stream': '.bin' # 默认未知类型
}
# --- 配置结束 ---


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
        # 如果模板展开为空，可能是该日没有 POTD，这在历史数据中很常见
        raise ValueError(f"无法展开 POTD 模板 ({date_str})。")
        
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

def download_image_file(url, mime_type, target_dir, date_str):
    """
    下载图片文件，并使用日期作为文件名基准。
    """
    ext = MIME_TO_EXT.get(mime_type, '.bin')
    # 文件名格式：YYYY-MM-DD.ext
    file_name = date_str + ext
    file_path = os.path.join(target_dir, file_name)
    
    # 检查文件是否已存在，实现增量更新
    if os.path.exists(file_path):
        print(f"   [SKIP] 图片已存在，跳过下载: {file_path}")
        return file_path
        
    print(f"   [DL] 正在下载图片到 {file_path}...")
    
    # 下载请求
    img_response = requests.get(url, stream=True, headers=HEADERS)
    img_response.raise_for_status()
    
    # 写入文件
    with open(file_path, 'wb') as f:
        for chunk in img_response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"   [DONE] 图片文件下载并保存完成。")
    return file_path


def save_metadata(details, date_str, target_dir):
    """
    保存图片的元数据文件。
    """
    metadata_file_name = date_str + '_meta.txt'
    metadata_file_path = os.path.join(target_dir, metadata_file_name)
    
    # 检查元数据文件是否已存在
    if os.path.exists(metadata_file_path):
        return
    
    result_content = (
        f"--- Wikimedia Commons Picture of the Day Metadata for {date_str} ---\n\n"
        f"File Name: {details['title'].replace('File:', '')}\n"
        f"Image URL: {details['url']}\n"
        f"MIME Type: {details['mime']}\n"
        f"Caption: {details['caption']}\n"
    )
    with open(metadata_file_path, 'w', encoding='utf-8') as f:
        f.write(result_content)


def process_date(current_date):
    """
    处理特定日期的 POTD 下载和保存。
    """
    date_str = current_date.strftime('%Y-%m-%d')
    print(f"\n>>>> 正在处理日期: {date_str} <<<<")
    
    # 构造目标目录: BASE_DOWNLOAD_DIR/YYYY/MM/
    target_dir = os.path.join(
        BASE_DOWNLOAD_DIR,
        current_date.strftime('%Y'),
        current_date.strftime('%m')
    )
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        # 1. 获取文件名
        filename = get_potd_filename(date_str)
        
        # 2. 获取图片详情
        details = get_image_details(filename)
        
        # 3. 下载实际图片文件（包含存在性检查和跳过逻辑）
        download_image_file(
            url=details['url'],
            mime_type=details['mime'],
            target_dir=target_dir,
            date_str=date_str
        )
        
        # 4. 保存元数据
        save_metadata(details, date_str, target_dir)
        
    except ValueError as e:
        # 无法找到 POTD 文件名，可能是当日无图片，跳过
        print(f"   [FAIL] 跳过: {e}")
    except requests.exceptions.HTTPError as e:
        # 网络请求失败，通常是 404 或 403
        print(f"   [FAIL] HTTP 错误 {e.response.status_code}，跳过该日期。")
    except Exception as e:
        print(f"   [FAIL] 发生意外错误，跳过该日期: {e}")


def fetch_and_save_wiki_picture():
    """
    批量获取从 START_YEAR 到今天的所有每日图片。
    """
    now_shanghai = datetime.now(SHANGHAI_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 确定起始日期
    start_date = datetime(START_YEAR, 1, 1, tzinfo=SHANGHAI_TZ)
    
    # 如果起始年份晚于当前年份，则以起始年份为准，否则以当前年份为准（防止下载未来日期）
    if start_date > now_shanghai:
        start_date = now_shanghai

    current_date = start_date
    
    print(f"🔥 任务开始：从 {start_date.strftime('%Y-%m-%d')} 到 {now_shanghai.strftime('%Y-%m-%d')} 批量下载 POTD。")
    
    while current_date <= now_shanghai:
        process_date(current_date)
        current_date += timedelta(days=1)
        
    print("\n🎉 批量下载任务完成！")


if __name__ == "__main__":
    fetch_and_save_wiki_picture()
