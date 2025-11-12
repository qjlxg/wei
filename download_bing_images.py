import requests
import datetime
import os
import re

# --- 配置 ---
# 1. API 基础 URL
BING_API_URL_BASE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt={}"
MARKETS_TO_CHECK = [
    # 亚洲及太平洋地区 (Asia/Pacific)
    "zh-CN", "zh-HK", "zh-TW", "ja-JP", "ko-KR", "en-IN", "en-AU", "en-NZ", "en-MY", 
    "en-PH", "en-SG", "en-ID", 
    # 欧洲地区 (Europe)
    "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT", "nl-NL", "sv-SE", "ru-RU", "tr-TR", 
    "pt-PT", "da-DK", "de-AT", "de-CH", "fi-FI", "fr-BE", "fr-CH", "nl-BE", "no-NO", 
    "pl-PL", 
    # 美洲地区 (The Americas)
    "en-US", "en-CA", "es-MX", "pt-BR", "es-AR", "es-CL", "es-US", "fr-CA", 
    # 中东及非洲地区 (Middle East/Africa)
    "en-ZA", "ar-XA",
]
# 3. 要下载图片的数量（今天 + 历史）
NUM_IMAGES_TO_FETCH = 8
# 4. 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080"
# 5. 目标文件夹 
OUTPUT_DIR = "bing_images_global_unique" 
# 6. 上海时区 (用于文件命名时间戳)
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# ----------------

def get_bing_data(market, index, count):
    """从指定的 Bing API URL 获取图片数据，并在失败时打印详细调试信息"""
    url = BING_API_URL_BASE.format(index, count, market)
    print(f"DEBUG: Attempting to fetch from market {market}, URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        
        # 检查 HTTP 状态码
        if response.status_code != 200:
            print(f"ERROR: Market {market} returned non-200 status code: {response.status_code}")
            return []
            
        # 尝试解析 JSON
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"ERROR: Market {market} response is not valid JSON. Response Text length: {len(response.text)}")
            return []

        images_data = data.get('images', [])
        for img in images_data:
            img['market_source'] = market
        
        if not images_data:
            print(f"WARNING: Market {market} returned data but 'images' array is empty.")
            
        return images_data
    
    except requests.exceptions.Timeout:
        print(f"ERROR: Market {market} request timed out after 10 seconds.")
        return []
    except requests.RequestException as e:
        print(f"FATAL ERROR: Network error fetching data from {market}: {e}")
        return []

def get_chinese_titles(image_urlbases):
    """专门从 zh-CN 市场获取中文标题，作为文件名附加标识"""
    print("\nFetching Chinese titles from zh-CN market for matching...")
    # 注意：get_bing_data 已经会打印 DEBUG 信息
    images_data_zh = get_bing_data("zh-CN", index=0, count=NUM_IMAGES_TO_FETCH)
    
    zh_titles = {}
    for img_zh in images_data_zh:
        urlbase = img_zh.get('urlbase')
        title = img_zh.get('copyright')
        if urlbase and urlbase in image_urlbases and title:
            zh_titles[urlbase] = title
            
    return zh_titles

def sanitize_filename(filename):
    """清理文件名中的非法字符，并替换所有非字母数字符号（包括URL查询符）"""
    # 替换非法字符和所有非字母数字、空格、下划线、点号的字符
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    # 截断过长的标题，避免文件名过长
    return safe_name[:80]

# 【使用 OHR 唯一 ID 提取实现严格去重】
def download_image_unified(base_url, start_date, title):
    """下载图片并保存到目标目录，使用统一文件名实现严格去重"""
    # 构建图片下载 URL - 使用原始 URLBase
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 构造目录: bing_images_global_unique/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # === 关键去重 ID 提取 (基于 OHR 标识) ===
    # 步骤 1: 清理 base_url，只保留文件名部分
    cleaned_url = base_url.split('/')[-1]

    # 步骤 2: 尝试从 OHR. 之后提取 ID，直到遇到第一个下划线 _ 为止
    # (例如从 OHR.ColosseumRome_DE-DE9770926344 提取 ColosseumRome)
    match = re.search(r'OHR\.([A-Za-z0-9]+)_', cleaned_url)

    if match:
        # 成功提取了核心名称
        unique_image_id = match.group(1)
    else:
        # 回退：如果格式异常，使用清理后的 URL 作为 ID
        unique_image_id = cleaned_url
        
    # 清理后的附加标题 (作为可读性标识，可选)
    safe_title = sanitize_filename(title)
    
    # 文件名：【最早时间戳】_【图片唯一ID】_【清理后的标题】.jpg
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    
    # 使用唯一图片 ID 确保去重
    filename = f"{timestamp}_{unique_image_id}_{safe_title}.jpg"
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
    
    # 用于存储所有不重复图片的元数据
    # 优化：确保记录的是 fullstartdate 最早的那个记录
    unique_images_map = {}
    
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images from {len(MARKETS_TO_CHECK)} global markets.")
    
    # 1. 遍历所有市场，收集数据并【记录最早的 fullstartdate】
    for market in MARKETS_TO_CHECK:
        images_data = get_bing_data(market, index=0, count=NUM_IMAGES_TO_FETCH)
        
        for img_data in images_data:
            urlbase = img_data.get('urlbase')
            # 默认为一个很大的字符串，以确保第一个记录被选中
            current_fullstartdate = img_data.get('fullstartdate', '999999999999')
            
            if urlbase:
                if urlbase not in unique_images_map:
                    # 第一次发现，直接记录
                    unique_images_map[urlbase] = img_data
                else:
                    # 第二次或之后发现，比较并记录更早的 fullstartdate
                    existing_fullstartdate = unique_images_map[urlbase].get('fullstartdate', '999999999999')
                    
                    # 如果当前找到的 fullstartdate 更早（字符串比较即可）
                    if current_fullstartdate < existing_fullstartdate:
                        # 更新元数据，以使用包含最早 fullstartdate 的那个记录
                        unique_images_map[urlbase] = img_data
    
    # 增加 DEBUG 信息，查看是否获取到了数据
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
        
        # 强制统一标题逻辑：优先使用中文标题，否则使用图片元数据中的 copyright
        default_title = img_data.get('copyright', 'bing_wallpaper_default')
        final_title = zh_titles_map.get(urlbase, default_title) 
        
        try:
            shanghai_datetime = None
            
            if utctime_str:
                # 方案 A: 使用 utctime，并转换为上海时区
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            elif hdate_str:
                # 方案 B: utctime 缺失，使用 hdate 和上海午夜时间 (00:00:00)
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                # 直接添加上海时区信息（注意：这里假设 hdate 指的是上海当地时间）
                shanghai_datetime = datetime.datetime(shanghai_date.year, shanghai_date.month, shanghai_date.day, 0, 0, 0, tzinfo=SHANGHAI_TZ)
            else:
                continue
            
            # **【最终调用】**：调用统一去重下载函数
            if download_image_unified(urlbase, shanghai_datetime, final_title):
                downloaded_count += 1
                
        except ValueError as e:
            print(f"Error parsing date/time for image {final_title}: {e}")
        
    print(f"\nScript finished. Total unique images processed: {len(images_to_download)}. New images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
