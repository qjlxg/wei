import requests
import datetime
import os
import re

# --- 配置 ---
# 1. API 基础 URL
BING_API_URL_BASE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt={}"
MARKETS_TO_CHECK = [
    # 亚洲及太平洋地区 (Asia/Pacific)
    "zh-CN", # 中国大陆 (China)
    "zh-HK", # 香港 (Hong Kong)
    "zh-TW", # 台湾 (Taiwan)
    "ja-JP", # 日本 (Japan)
    "ko-KR", # 韩国 (South Korea)
    "en-IN", # 印度 (India)
    "en-AU", # 澳大利亚 (Australia)
    "en-NZ", # 新西兰 (New Zealand)
    "en-MY", # 马来西亚 (Malaysia)
    "en-PH", # 菲律宾 (Philippines)
    "en-SG", # 新加坡 (Singapore)
    "en-ID", # 印度尼西亚 (Indonesia)
   
    # 欧洲地区 (Europe)
    "en-GB", # 英国 (United Kingdom)
    "de-DE", # 德国 (Germany)
    "fr-FR", # 法国 (France)
    "es-ES", # 西班牙 (Spain)
    "it-IT", # 意大利 (Italy)
    "nl-NL", # 荷兰 (Netherlands)
    "sv-SE", # 瑞典 (Sweden)
    "ru-RU", # 俄罗斯 (Russia)
    "tr-TR", # 土耳其 (Turkey)
    "pt-PT", # 葡萄牙 (Portugal)
    "da-DK", # 丹麦 (Denmark)
    "de-AT", # 奥地利 (Austria)
    "de-CH", # 瑞士 (German)
    "fi-FI", # 芬兰 (Finland)
    "fr-BE", # 比利时 (French)
    "fr-CH", # 瑞士 (French)
    "nl-BE", # 比利时 (Dutch)
    "no-NO", # 挪威 (Norway)
    "pl-PL", # 波兰 (Poland)
   
    # 美洲地区 (The Americas)
    "en-US", # 美国 (United States)
    "en-CA", # 加拿大 (Canada)
    "es-MX", # 墨西哥 (Mexico)
    "pt-BR", # 巴西 (Brazil)
    "es-AR", # 阿根廷 (Argentina)
    "es-CL", # 智利 (Chile)
    "es-US", # 美国 (Spanish)
    "fr-CA", # 加拿大 (French)
   
    # 中东及非洲地区 (Middle East/Africa)
    "en-ZA", # 南非 (South Africa)
    "ar-XA", # 阿拉伯语地区 (General Arabic)
]
# 3. 要下载图片的数量（今天 + 历史）
NUM_IMAGES_TO_FETCH = 8
# 4. 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080"
# 5. 目标文件夹
OUTPUT_DIR = "bing_images_global_unique" # 建议修改为这个名称，以区分之前的重复文件
# 6. 上海时区 (用于文件命名时间戳)
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# ----------------
def get_bing_data(market, index, count):
    """从指定的 Bing API URL 获取图片数据"""
    url = BING_API_URL_BASE.format(index, count, market)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # 增加市场信息到每个图片数据中，用于追踪来源
        images_data = response.json().get('images', [])
        for img in images_data:
            img['market_source'] = market
        return images_data
    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return []
def get_chinese_titles(image_urlbases):
    """
    专门从 zh-CN 市场获取中文标题，作为所有去重图片的统一标题来源。
    """
    print("Fetching Chinese titles from zh-CN market for matching...")
    images_data_zh = get_bing_data("zh-CN", index=0, count=NUM_IMAGES_TO_FETCH)
  
    zh_titles = {}
    for img_zh in images_data_zh:
        urlbase = img_zh.get('urlbase')
        title = img_zh.get('copyright')
        if urlbase in image_urlbases and title:
            zh_titles[urlbase] = title
          
    return zh_titles
def sanitize_filename(filename):
    """清理文件名中的非法字符，保留原始标题主体"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

# **【关键修改】**：下载函数不再接受 market_source，且文件名中不包含市场标识
def download_image_unified(base_url, start_date, title):
    """下载图片并保存到目标目录，使用统一文件名实现严格去重"""
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
  
    # 构造目录: bing_images_global_unique/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
  
    # 清理标题
    safe_title = sanitize_filename(title)
  
    # 文件名: 年月日_时分秒_清理后的原始标题.jpg (严格统一格式)
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    # **【关键修改】**：文件名中不再包含 {market_source}
    filename = f"{timestamp}_{safe_title}.jpg"
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
    """主函数 - 聚合多市场数据并去重下载"""
  
    # 用于存储所有不重复图片的元数据
    unique_images_map = {}
   
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images from {len(MARKETS_TO_CHECK)} global markets.")
    # 1. 遍历所有市场，收集数据并去重
    for market in MARKETS_TO_CHECK:
        print(f"-> Fetching data from market: {market}...")
        images_data = get_bing_data(market, index=0, count=NUM_IMAGES_TO_FETCH)
       
        for img_data in images_data:
            urlbase = img_data.get('urlbase')
            # 使用 urlbase 进行去重：只记录第一次发现的图片数据
            if urlbase and urlbase not in unique_images_map:
                unique_images_map[urlbase] = img_data
  
    if not unique_images_map:
        print("Failed to fetch any unique image data. Exiting.")
        return
    # 2. 准备下载列表和获取中文标题
    images_to_download = list(unique_images_map.values())
    all_urlbases = set(unique_images_map.keys())
   
    # 获取中文标题映射
    zh_titles_map = get_chinese_titles(all_urlbases)
   
    print(f"Found a total of {len(images_to_download)} unique images to process.")
   
    downloaded_count = 0
  
    # 3. 遍历下载
    for img_data in images_to_download:
        hdate_str = img_data.get('startdate')
        utctime_str = img_data.get('fullstartdate')
        urlbase = img_data.get('urlbase')
      
        # 统一标题逻辑：优先使用中文标题，否则使用图片元数据中的 copyright
        default_title = img_data.get('copyright', 'bing_wallpaper_default')
        # **【关键修改】**：强制所有重复图片使用统一标题，以保证文件名一致
        final_title = zh_titles_map.get(urlbase, default_title) 
       
        try:
            shanghai_datetime = None
          
            if utctime_str:
                # 方案 A: 使用 utctime
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            elif hdate_str:
                # 方案 B: utctime 缺失，使用 hdate 和上海午夜时间 (00:00:00)
                print(f"Warning: utctime missing for {final_title}. Using hdate with 00:00:00 Shanghai time.")
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
            else:
                 print(f"Skipping image {urlbase} due to missing date data.")
                 continue
            
            # **【关键修改】**：调用新的 download_image_unified 函数
            if download_image_unified(urlbase, shanghai_datetime, final_title):
                downloaded_count += 1
              
        except ValueError as e:
            print(f"Error parsing date/time for image {final_title}: {e}")
      
    print(f"Script finished. Total unique images processed: {len(images_to_download)}. New images downloaded: {downloaded_count}")
if __name__ == "__main__":
    main()
