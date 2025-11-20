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
    'User-Agent': 'GitHubActionWikiPotdBatchDownloader/6.1 (contact: YourContact@example.com)'
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
    'application/octet-stream': '.bin'
}
# --- 配置结束 ---


def get_potd_filename(date_str):
    """
    第一步：通过展开 POTD 模板获取当天的图片文件名。
    """
    template_text = f"{{{{Potd/{date_str}}}}}"
    params = {
        "action": "expandtemplates",
        "format": "json",
        "prop": "wikitext",
        "text": template_text
    }
    
    # *** 关键修改：添加 timeout ***
    response = requests.get(API_ENDPOINT, headers=HEADERS, params=params, timeout=10)
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
        raise ValueError(f"无法展开 POTD 模板 ({date_str})。")
        
    return wikitext

def get_image_details(filename):
    """
    第二步：获取图片文件的 URL 和 MIME 类型。
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|mime"
    }
    
    # *** 关键修改：添加 timeout ***
    response = requests.get(API_ENDPOINT, headers=HEADERS, params=params, timeout=10)
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
        
    return {
        'url': image_info.get('url'),
        'mime': image_info.get('mime')
    }

def download_image_file(url, mime_type, target_dir, date_str):
    """
    下载图片文件，并使用 YYYY-MM-DD.ext 作为文件名。
    """
    ext = MIME_TO_EXT.get(mime_type, '.bin')
    file_name = date_str + ext
    file_path = os.path.join(target_dir, file_name)
    
    if os.path.exists(file_path):
        print(f"   [SKIP] 图片已存在，跳过下载: {file_path}")
        return
        
    print(f"   [DL] 正在下载图片到 {file_path}...")
    
    # *** 关键修改：添加 timeout (图片下载允许更长) ***
    img_response = requests.get(url, stream=True, headers=HEADERS, timeout=30)
    img_response.raise_for_status()
    
    with open(file_path, 'wb') as f:
        for chunk in img_response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    print(f"   [DONE] 图片文件下载并保存完成。")


def process_date(current_date):
    """
    处理特定日期的 POTD 下载。
    """
    date_str = current_date.strftime('%Y-%m-%d')
    # ... 省略目录创建逻辑 ...
    target_dir = os.path.join(
        BASE_DOWNLOAD_DIR,
        current_date.strftime('%Y'),
        current_date.strftime('%m')
    )
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"\n>>>> 正在处理日期: {date_str} <<<<") # 此处 print 也会被缓冲

    try:
        filename = get_potd_filename(date_str)
        details = get_image_details(filename)
        download_image_file(
            url=details['url'],
            mime_type=details['mime'],
            target_dir=target_dir,
            date_str=date_str
        )
        
    except ValueError as e:
        print(f"   [FAIL] 跳过 (无图片或 API 错误): {e}")
    except requests.exceptions.Timeout:
         print(f"   [FAIL] 请求超时 (Timeout)，跳过该日期。")
    except requests.exceptions.HTTPError as e:
        print(f"   [FAIL] HTTP 错误 {e.response.status_code}，跳过该日期。")
    except Exception as e:
        print(f"   [FAIL] 发生意外错误，跳过该日期: {e}")


def fetch_and_save_wiki_picture():
    """
    批量获取从 START_YEAR 到今天的所有每日图片。
    """
    now_shanghai = datetime.now(SHANGHAI_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = datetime(START_YEAR, 1, 1, tzinfo=SHANGHAI_TZ)
    if start_date > now_shanghai:
        start_date = now_shanghai

    current_date = start_date
    
    # *** 关键修改：强制刷新输出缓冲区 ***
    print(f"🔥 任务开始：从 {start_date.strftime('%Y-%m-%d')} 到 {now_shanghai.strftime('%Y-%m-%d')} 批量下载 POTD。", flush=True)
    
    while current_date <= now_shanghai:
        process_date(current_date)
        current_date += timedelta(days=1)
        
    print("\n🎉 批量下载任务完成！", flush=True)


if __name__ == "__main__":
    fetch_and_save_wiki_picture()
