import requests
import datetime
import os
import re

# --- 配置 ---
# 仅使用最稳定的数据源 (en-US)
BING_API_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=en-US"
NUM_IMAGES_TO_FETCH = 8
RESOLUTION = "1920x1080" 
OUTPUT_DIR = "bing_images"
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# ----------------

def get_bing_data(api_url, index, count):
    """从指定的 Bing API URL 获取图片数据"""
    url = api_url.format(index, count)
    print(f"DEBUG: Attempting to fetch data from: {url}") 
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        images = json_data.get('images', [])
        
        if not images:
             print(f"DEBUG: API returned 200 OK, but 'images' list is empty or missing.")
             print(f"DEBUG: Full API response keys: {list(json_data.keys())}")
        
        return images
    except requests.RequestException as e:
        print(f"ERROR: Request failed for API: {e}")
        return []

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(base_url, start_date, title):
    # (保持不变的下载逻辑...)
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    safe_title = sanitize_filename(title)
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
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images using the stable en-US market...")
    images = get_bing_data(BING_API_URL, index=0, count=NUM_IMAGES_TO_FETCH)
    
    if not images:
        print("Failed to fetch any image data or API data is malformed. Exiting.")
        return

    downloaded_count = 0
    
    for img_data in images:
        hdate_str = img_data.get('hdate')
        utctime_str = img_data.get('utctime')
        urlbase = img_data.get('urlbase')
        title = img_data.get('copyright', 'bing_wallpaper_en')
        
        if not hdate_str or not urlbase:
            print(f"Skipping image (EN): Missing hdate/urlbase for title: {title}")
            continue

        try:
            shanghai_datetime = None
            
            if utctime_str:
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            else:
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
            
            if download_image(urlbase, shanghai_datetime, title):
                downloaded_count += 1
                
        except ValueError as e:
            print(f"Error parsing date/time for image {title}: {e}")
        
    print(f"Script finished. Total new images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
