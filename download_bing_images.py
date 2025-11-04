import requests
import datetime
import os
import re

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
        response.raise_for_status()
        return response.json().get('images', [])
    except requests.RequestException as e:
        print(f"Error fetching data from Bing API at index {index}: {e}")
        return []

def sanitize_filename(filename):
    """清理文件名中的非法字符，保留中文和常见标点符号"""
    # 移除文件路径中的非法字符（例如 \ / : * ? " < > |）
    # 同时将文件名中的空格替换为下划线，提高跨平台兼容性
    
    # 替换所有不可用于文件名的特殊字符为空格
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    # 将多个空格替换为一个下划线
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    
    return safe_name

def download_image(base_url, start_date, title):
    """下载图片并保存到以年/月命名的目录中，文件名包含时间戳和清理后的标题"""
    # 构造完整图片 URL
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
    
    # 根据开始日期确定保存路径和文件名
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    
    # 目标目录: bing_images/年/月
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
    
    # 清理标题，以保证操作系统兼容性，但保留原始标题主体
    safe_title = sanitize_filename(title)
    
    # 文件名: 年月日_时间戳_清理后的原始标题.jpg
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
        hdate_str = img_data.get('hdate') # 格式: YYYYMMDD
        utctime_str = img_data.get('utctime') # 格式: YYYYMMDDHHMM (可能缺失)
        # 获取原始标题，包括版权信息
        title = img_data.get('copyright', 'bing_wallpaper')
        
        if not hdate_str:
            print(f"Skipping image due to missing hdate info: {title}")
            continue

        try:
            shanghai_datetime = None
            
            if utctime_str:
                # 方案 A: 如果 utctime 存在，按原逻辑处理
                # 解析日期和时间 (UTC)
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                # 转换为上海时区
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            else:
                # 方案 B: 如果 utctime 缺失，使用 hdate 和上海午夜时间作为时间戳
                print(f"Warning: utctime missing for {title}. Using hdate with 00:00:00 Shanghai time.")
                # 构造一个上海时区的午夜时间
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
            
            # 下载图片
            if download_image(img_data['urlbase'], shanghai_datetime, title):
                downloaded_count += 1
                
        except ValueError as e:
            print(f"Error parsing date/time for image {title}: {e}")
        
    print(f"Script finished. Total new images downloaded: {downloaded_count}")

if __name__ == "__main__":
    main()
