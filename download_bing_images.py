import requests
import datetime
import os
import re

# --- 配置 ---
# 1. 稳定数据源 (用于获取可靠的 hdate/utctime)
BING_API_URL_DATA = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=en-US"
# 2. 中文标题源 (用于获取中文标题)
BING_API_URL_TITLE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=zh-CN"
# 要下载图片的数量（今天 + 历史）
NUM_IMAGES_TO_FETCH = 8
# 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080" 
# 目标文件夹
OUTPUT_DIR = "bing_images"
# 上海时区
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# ----------------

def get_bing_data(api_url, index, count):
    """从指定的 Bing API URL 获取图片数据"""
    url = api_url.format(index, count)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get('images', [])
    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return []

def get_chinese_titles(images_data_en):
    """获取中文市场（zh-CN）的图片标题，用于匹配英文数据"""
    print("Fetching Chinese titles from zh-CN market...")
    images_data_zh = get_bing_data(BING_API_URL_TITLE, index=0, count=NUM_IMAGES_TO_FETCH)
    
    zh_titles = {}
    for img_zh in images_data_zh:
        # 使用 urlbase 作为唯一键来匹配不同市场的图片
        urlbase = img_zh.get('urlbase')
        title = img_zh.get('copyright')
        if urlbase and title:
            zh_titles[urlbase] = title
            
    return zh_titles

def sanitize_filename(filename):
    """清理文件名中的非法字符，保留原始标题主体"""
    # 移除文件路径中的非法字符（例如 \ / : * ? " < > |）
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    # 将多个空格替换为一个下划线
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(base_url, start_date, title):
    """下载图片并保存到目标目录"""
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 构造目录: bing_images/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # 清理标题
    safe_title = sanitize_filename(title)
    
    # 文件名: 年月日_时分秒_清理后的原始标题.jpg
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)

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
    """主函数"""
    
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images using the stable en-US market...")
    images_en = get_bing_data(BING_API_URL_DATA, index=0, count=NUM_IMAGES_TO_FETCH)
    
    if not images_en:
        print("Failed to fetch any image data from the stable market. Exiting.")
        return

    # 获取中文标题映射
    zh_titles_map = get_chinese_titles(images_en)
    
    downloaded_count = 0
    
    for img_data in images_en:
        hdate_str = img_data.get('hdate') # YYYYMMDD
        utctime_str = img_data.get('utctime') # YYYYMMDDHHMM (可能缺失)
        urlbase = img_data.get('urlbase')
        
        if not hdate_str or not urlbase:
            print(f"Skipping image due to missing critical data (hdate/urlbase).")
            continue
            
        # 优先使用中文标题，否则使用英文标题
        final_title = zh_titles_map.get(urlbase, img_data.get('copyright', 'bing_wallpaper_en'))

        try:
            shanghai_datetime = None
            
            if utctime_str:
                # 方案 A: 使用 utctime
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            else:
                # 方案 B: utctime 缺失，使用 hdate 和上海午夜时间 (00:00:00)
                print(f"Warning: utctime missing for {final_title}. Using hdate with 00:00:00 Shanghai time.")
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
            
            # 下载图片
            if download_image(urlbase, shanghai_datetime, final_title):
                downloaded_count += 1
                
        except ValueError as e:
            print(f"Error parsing date/time for image {final_title}: {e}")
        
    print(f"Script finished. Total new images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
