import requests
import datetime
import os
import re

# --- 配置 ---
# (市场列表等配置保持不变，为节省篇幅省略)
BING_API_URL_BASE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt={}"
MARKETS_TO_CHECK = [
    "zh-CN", "zh-HK", "zh-TW", "ja-JP", "ko-KR", "en-IN", "en-AU", "en-NZ", "en-MY", 
    "en-PH", "en-SG", "en-ID", "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT", "nl-NL", 
    "sv-SE", "ru-RU", "tr-TR", "pt-PT", "da-DK", "de-AT", "de-CH", "fi-FI", "fr-BE", 
    "fr-CH", "nl-BE", "no-NO", "pl-PL", "en-US", "en-CA", "es-MX", "pt-BR", "es-AR", 
    "es-CL", "es-US", "fr-CA", "en-ZA", "ar-XA"
]
NUM_IMAGES_TO_FETCH = 8
RESOLUTION = "1920x1080"
OUTPUT_DIR = "bing_images_global_unique" 
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# ----------------

def get_bing_data(market, index, count):
    """从指定的 Bing API URL 获取图片数据"""
    url = BING_API_URL_BASE.format(index, count, market)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        images_data = response.json().get('images', [])
        for img in images_data:
            img['market_source'] = market
        return images_data
    except requests.RequestException as e:
        return []

def get_chinese_titles(image_urlbases):
    """从 zh-CN 市场获取中文标题，作为文件名附加标识"""
    images_data_zh = get_bing_data("zh-CN", index=0, count=NUM_IMAGES_TO_FETCH)
    zh_titles = {}
    for img_zh in images_data_zh:
        urlbase = img_zh.get('urlbase')
        title = img_zh.get('copyright')
        if urlbase and urlbase in image_urlbases and title:
            zh_titles[urlbase] = title
    return zh_titles

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    # 截断过长的标题，避免文件名过长
    return safe_name[:80] 

# 【核心去重函数】: 强制使用 URLBase 作为文件名的一部分
def download_image_unified(base_url, start_date, title):
    """下载图片并保存到目标目录，使用统一文件名实现严格去重"""
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 构造目录: bing_images_global_unique/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # 从 urlbase 中提取图片ID部分 (例如：/az/hprichbg/rb/Colosseum_ROW2815617303)
    # 我们只需要最后一部分作为唯一ID：Colosseum_ROW2815617303
    urlbase_segment = base_url.split('/')[-1]

    # 清理后的附加标题 (作为可读性标识，可选)
    safe_title = sanitize_filename(title)
    
    # 文件名：【最早时间戳】_【URLBase唯一ID】_【清理后的标题】.jpg
    # 严格去重只依赖前两部分，第三部分仅为方便查看
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{urlbase_segment}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)
    
    # 核心去重检查：只要文件名相同，就跳过
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading {title} to {filepath}")
    
    try:
        img_response = requests.get(image_url, stream=True, timeout=15)
        img_response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully saved: {filepath}")
        return True
    except requests.RequestException as e:
        print(f"Error downloading image {image_url}: {e}")
        return False

def main():
    """主函数 - 聚合多市场数据并去重下载（包含最早时间戳和URLBase命名优化）"""
    
    unique_images_map = {}
    
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images from {len(MARKETS_TO_CHECK)} global markets.")
    
    # 1. 遍历所有市场，收集数据并【记录最早的 fullstartdate】
    for market in MARKETS_TO_CHECK:
        images_data = get_bing_data(market, index=0, count=NUM_IMAGES_TO_FETCH)
        
        for img_data in images_data:
            urlbase = img_data.get('urlbase')
            current_fullstartdate = img_data.get('fullstartdate', '999999999999')
            
            if urlbase:
                if urlbase not in unique_images_map:
                    # 第一次发现，直接记录
                    unique_images_map[urlbase] = img_data
                else:
                    # 第二次或之后发现，比较并记录更早的 fullstartdate
                    existing_fullstartdate = unique_images_map[urlbase].get('fullstartdate', '999999999999')
                    
                    if current_fullstartdate < existing_fullstartdate:
                        # 更新元数据，以使用包含最早 fullstartdate 的那个记录
                        unique_images_map[urlbase] = img_data
    
    if not unique_images_map:
        print("Failed to fetch any unique image data. Exiting.")
        return

    # 2. 准备下载列表和获取中文标题 (作为附加信息)
    images_to_download = list(unique_images_map.values())
    all_urlbases = set(unique_images_map.keys())
    
    # 获取中文标题映射
    zh_titles_map = get_chinese_titles(all_urlbases)
    
    print(f"\nFound a total of {len(images_to_download)} unique images to process.")
    
    downloaded_count = 0
    
    # 3. 遍历下载
    for img_data in images_to_download:
        hdate_str = img_data.get('startdate')
        utctime_str = img_data.get('fullstartdate')
        urlbase = img_data.get('urlbase')
        
        # 强制统一标题逻辑：优先使用中文标题，否则使用
