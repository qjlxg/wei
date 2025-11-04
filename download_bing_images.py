import requests
import datetime
import os
import time

# Bing 图片 API
BING_API_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=zh-CN"
# 要下载图片的数量（今天 + 7天历史 = 8张）
NUM_IMAGES_TO_FETCH = 8
# 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080" 
# 目标文件夹
OUTPUT_DIR = "bing_images"
# 上海时区
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))

def get_image_data(index, count):
    """从 Bing API 获取图片数据"""
    url = BING_API_URL.format(index, count)
    try:
        response = requests.get(url)
        response.raise_for_status() # 检查HTTP错误
        return response.json().get('images', [])
    except requests.RequestException as e:
        print(f"Error fetching data from Bing API at index {index}: {e}")
        return []

def download_image(base_url, start_date, title):
    """下载图片并保存到以年/月命名的目录中，文件名包含时间戳和标题"""
    # 构造完整图片 URL
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 根据开始日期确定保存路径和文件名
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    
    # 目标目录: bing_images/年/月
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # 文件名: 年月日_时间戳_标题.jpg
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading {image_url} to {filepath}")
    
    try:
        # 下载图片
        img_response = requests.get(image_url, stream=True)
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
    
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images from Bing API (including history)...")
    images = get_image_data(index=0, count=NUM_IMAGES_TO_FETCH)
    
    downloaded_count = 0
    
    for img_data in images:
        hdate_str = img_data.get('hdate') 
        utctime_str = img_data.get('utctime') 
        title = img_data.get('copyright', 'bing_wallpaper')
        
        if not hdate_str or not utctime_str:
            print(f"Skipping image due to missing date/time info: {title}")
            continue

        try:
            # 解析日期和时间 (UTC)
            utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
            # 转换为上海时区
            shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            
            # 下载图片
            if download_image(img_data['urlbase'], shanghai_datetime, title):
                downloaded_count += 1
                
        except ValueError as e:
            print(f"Error parsing date/time for image {title}: {e}")
        
    print(f"Script finished. Total new images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
