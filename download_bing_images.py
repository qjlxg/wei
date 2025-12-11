import requests
import datetime
import os
import re

# --- V6.0 配置与市场优先级 ---
# 1. API 基础 URL
BING_API_URL_BASE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt={}"

# 2. 【核心优化】定义市场优先级列表
# 优先级：越靠前越高。当核心 ID (img_id) 冲突时，保留优先级最高的市场的元数据。
# 越是内容独特的市场（如 zh-CN, ja-JP），优先级应越高。
MARKET_PRIORITIES = [
    "zh-CN", "ja-JP", "ko-KR",  # 亚洲独特内容（高优先级）
    "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR", "en-CA", "en-AU", # 主要国际市场
    "en-IN", "es-MX", "ar-XA", "en-ZA", # 其他重要市场
    # 所有未列出的市场将获得最低的优先级
]
PRIORITY_MAP = {market: i for i, market in enumerate(MARKET_PRIORITIES)}
LOWEST_PRIORITY_RANK = len(MARKET_PRIORITIES) # 列表外的市场优先级

# 3. V5.2 最终合并版 MARKETS_TO_CHECK (总共约 85 个)
MARKETS_TO_CHECK = [
    # 亚洲及太平洋地区 (Asia/Pacific) - (约 35 个)
    "zh-CN", "zh-HK", "zh-TW", "ja-JP", "ko-KR", "en-IN", "en-AU", "en-NZ", "en-MY", 
    "en-PH", "en-SG", "en-ID", "th-TH", "vi-VN", "id-ID", "ms-MY", "hi-IN", "bn-IN", 
    "ta-IN", "en-TH", "en-PK", "en-BD", "en-LK", 
    
    # 欧洲地区 (Europe) - (约 30 个)
    "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT", "nl-NL", "sv-SE", "ru-RU", "tr-TR", 
    "pt-PT", "da-DK", "de-AT", "de-CH", "fi-FI", "fr-BE", "fr-CH", "nl-BE", "no-NO", 
    "pl-PL", "bg-BG", "cs-CZ", "el-GR", "hu-HU", "ro-RO", "sk-SK", "sl-SI", "hr-HR", 
    "lt-LT", "lv-LV", "et-EE", "uk-UA", "en-IE",
    
    # 美洲地区 (The Americas) - (约 20 个)
    "en-US", "en-CA", "es-MX", "pt-BR", "es-AR", "es-CL", "es-US", "fr-CA", 
    "es-CO", "es-PE", "es-VE", "es-EC", "es-BO", "es-PY", "es-UY", "es-PR", "es-DO", 
    
    # 中东及非洲地区 (Middle East/Africa) - (约 20 个)
    "en-ZA", "ar-XA", "ar-SA", "ar-AE", "ar-EG", "ar-MA", "he-IL", "fr-DZ", "fr-MA", 
    "en-KE", "en-NG", "sw-KE", "pt-AO", "ar-IQ", "ar-JO", "en-AE", "en-BH", "en-KW", 
    "en-OM", "en-QA", "en-SA", "en-IL", "en-LB", "en-JO", "en-CY",
]
# -----------------------------------------------

# 4. 【修改：下载历史图片的数量】
NUM_IMAGES_TO_FETCH = 60 

# 5. 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080"
# 6. 目标文件夹 
OUTPUT_DIR = "bing_images_global_unique" 
# 7. 上海时区 (用于文件命名时间戳)
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
        # 为每个图片数据添加市场来源标记
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

def extract_unique_id(base_url):
    """
    从完整的 urlbase 中提取唯一的、跨市场不变的核心图片标识符。
    例如：从 th?id=OHR.ColosseumRome_DE-DE9770926344 提取 ColosseumRome
    """
    cleaned_url = base_url.split('/')[-1]
    # 尝试从 OHR. 之后提取 ID，直到遇到第一个下划线 _ 为止
    match = re.search(r'OHR\.([A-Za-z0-9]+)_', cleaned_url)

    if match:
        return match.group(1)
    else:
        # 回退：如果格式异常，使用清理后的 URL 作为 ID
        return cleaned_url

def get_chinese_titles(image_ids):
    """专门从 zh-CN 市场获取中文标题，现在使用 ID 作为键"""
    print("\nFetching Chinese titles from zh-CN market for matching...")
    images_data_zh = get_bing_data("zh-CN", index=0, count=NUM_IMAGES_TO_FETCH)
    
    zh_titles = {}
    for img_zh in images_data_zh:
        img_id = extract_unique_id(img_zh.get('urlbase', ''))
        # title 是 '© XXXX (通过 XXXX)' 格式
        title = img_zh.get('copyright')
        if img_id and img_id in image_ids and title:
            zh_titles[img_id] = title
            
    return zh_titles

def sanitize_filename(filename):
    """清理文件名中的非法字符，并替换所有非字母数字符号（包括URL查询符）"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    # 截断过长的标题，避免文件名过长
    return safe_name[:80]

def download_image_unified(base_url, start_date, title, unique_image_id):
    """下载图片并保存到目标目录，使用【核心 ID】实现严格去重"""
    # 构建图片下载 URL - 使用原始 URLBase
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 构造目录: bing_images_global_unique/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # 清理后的附加标题 (作为可读性标识，可选)
    safe_title = sanitize_filename(title)
    
    # 文件名：【最早时间戳】_【图片唯一ID】_【清理后的标题】.jpg
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    
    # 【核心】使用传入的 unique_image_id 确保文件名统一
    filename = f"{timestamp}_{unique_image_id}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)
    
    # 核心去重检查：只要文件名相同，就跳过
    if os.path.exists(filepath):
        print(f"INFO: File already exists: {filepath}. Skipping download.")
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
        print(f"ERROR: Error downloading image {image_url}: {e}")
        return False

def main():
    """主函数 - 聚合多市场数据并【基于核心 ID 和优先级】去重下载"""
    
    # 键是 unique_image_id
    unique_images_map = {}
    
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images from {len(MARKETS_TO_CHECK)} global markets.")
    
    # 1. 遍历所有市场，收集数据并【基于优先级进行智能覆盖】
    for market in MARKETS_TO_CHECK:
        # 获取当前市场的优先级，如果未在列表中定义，则赋予最低优先级
        current_priority = PRIORITY_MAP.get(market, LOWEST_PRIORITY_RANK) 
        images_data = get_bing_data(market, index=0, count=NUM_IMAGES_TO_FETCH)
        
        for img_data in images_data:
            urlbase = img_data.get('urlbase')
            # 提取核心 ID 作为去重键
            img_id = extract_unique_id(urlbase)
            
            # 默认为一个很大的字符串，以确保第一个记录被选中
            current_fullstartdate = img_data.get('fullstartdate', '999999999999')
            
            if img_id:
                if img_id not in unique_images_map:
                    # 第一次发现，直接记录
                    unique_images_map[img_id] = img_data
                else:
                    # 第二次或之后发现，进行智能比较
                    existing_data = unique_images_map[img_id]
                    existing_market = existing_data.get('market_source', 'N/A')
                    existing_priority = PRIORITY_MAP.get(existing_market, LOWEST_PRIORITY_RANK)
                    
                    # 规则 A: 比较优先级。优先级数字越小，优先级越高。
                    if current_priority < existing_priority:
                        # 当前市场的优先级更高，直接覆盖旧数据
                        unique_images_map[img_id] = img_data
                    
                    # 规则 B: 如果优先级相同，则恢复到原来的“最早日期优先”逻辑
                    elif current_priority == existing_priority:
                        existing_fullstartdate = existing_data.get('fullstartdate', '999999999999')
                        
                        if current_fullstartdate < existing_fullstartdate:
                            # 当前市场的日期更早，覆盖旧数据
                            unique_images_map[img_id] = img_data
                        # else: 日期更晚，保持现有数据不变
    
    # 检查是否获取到了数据
    if not unique_images_map:
        print("Failed to fetch any unique image data. Exiting.")
        return

    # 2. 准备下载列表和获取中文标题 
    all_image_ids = set(unique_images_map.keys())
    
    # 获取中文标题映射
    zh_titles_map = get_chinese_titles(all_image_ids)
    
    print(f"\nFound a total of {len(unique_images_map)} unique images to process.")
    
    downloaded_count = 0
    
    # 3. 遍历下载
    for img_id, img_data in unique_images_map.items():
        hdate_str = img_data.get('startdate')
        utctime_str = img_data.get('fullstartdate')
        urlbase = img_data.get('urlbase')
        source_market = img_data.get('market_source', 'N/A') # 记录最终被选中的市场

        # 强制统一标题逻辑：优先使用中文标题，否则使用图片元数据中的 copyright
        default_title = img_data.get('copyright', 'bing_wallpaper_default')
        final_title = zh_titles_map.get(img_id, default_title) 
        
        try:
            shanghai_datetime = None
            
            if utctime_str:
                # 方案 A: 使用 utctime，并转换为上海时区
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            elif hdate_str:
                # 方案 B: utctime 缺失，使用 hdate 和上海午夜时间 (00:00:00)
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = datetime.datetime(shanghai_date.year, shanghai_date.month, shanghai_date.day, 0, 0, 0, tzinfo=SHANGHAI_TZ)
            else:
                continue
            
            # **【核心调用】**：传入提取出的 img_id
            if download_image_unified(urlbase, shanghai_datetime, final_title, img_id):
                downloaded_count += 1
                print(f"INFO: Image ID {img_id} (Source: {source_market}) was successfully downloaded.")
            else:
                print(f"INFO: Image ID {img_id} (Source: {source_market}) skipped. File already exists or failed download.")

        except ValueError as e:
            print(f"Error parsing date/time for image {final_title}: {e}")
        
    print(f"\nScript finished. Total unique images processed: {len(unique_images_map)}. New images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
