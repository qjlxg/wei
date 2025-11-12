import requests
import os
import re
import sys
from datetime import datetime, timedelta

# --- 配置 ---

# 1. API 基础 URL
API_URL = "https://api.nasa.gov/planetary/apod"

# 2. **批量下载配置：起始日期**
# 脚本将从 START_DATE 一直到运行脚本的今天，逐日下载。
# 格式必须是 YYYY-MM-DD
START_DATE = "2025-10-30" 

# 3. 目标文件夹的根目录
BASE_OUTPUT_DIR = "nasa_apod_wallpapers"

# 4. 环境变量中的 NASA API KEY 名称
API_KEY_ENV_VAR = "NASA_API_KEY"

# ----------------

def set_action_output(new_files_downloaded):
    """使用 Environment File 输出状态给 GitHub Actions"""
    output_key = "commit_needed"
    output_value = "true" if new_files_downloaded else "false"
    
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{output_key}={output_value}\n")
    else:
        print(f"Output for Actions: {output_key}={output_value}") 

def download_image(image_url, title, date):
    """下载图片并保存到目标目录 (YYYY/MM 结构)"""
    
    year = date[:4]
    month = date[5:7]
    current_output_dir = os.path.join(BASE_OUTPUT_DIR, year, month)
    os.makedirs(current_output_dir, exist_ok=True)
    
    # 文件名: YYYY-MM-DD_标题.jpg
    title_safe = title.replace(' ', '_').replace('/', '_')
    raw_filename = f"{date}_{title_safe}.jpg"
    
    # 移除文件名中所有非法或不必要的字符
    safe_filename = "".join(c for c in raw_filename if c.isalnum() or c in ('_', '.', '-')).rstrip()
    filepath = os.path.join(current_output_dir, safe_filename)
    
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading {title} to {filepath}")
    
    try:
        img_response = requests.get(image_url, stream=True, timeout=30)
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
    """主函数 - 循环获取 APOD 并下载"""
    
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"FATAL: {API_KEY_ENV_VAR} environment variable not set. Please set the Secret to DEMO_KEY.")
        set_action_output(False)
        sys.exit(1)

    start_date_obj = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    end_date_obj = datetime.now().date()
    
    if start_date_obj > end_date_obj:
        print("Start date is in the future. Exiting.")
        set_action_output(False)
        return

    delta = end_date_obj - start_date_obj
    downloaded_count = 0
    new_files_downloaded = False
    
    print(f"Starting batch download from {START_DATE} to {end_date_obj.strftime('%Y-%m-%d')}. Total {delta.days + 1} days to check.")

    for i in range(delta.days + 1):
        current_date_obj = start_date_obj + timedelta(days=i)
        current_date_str = current_date_obj.strftime("%Y-%m-%d")
        
        print(f"\n--- Checking {current_date_str} ---")

        params = {
            'api_key': api_key,
            'date': current_date_str,  # 使用 date 参数请求指定日期的图片
            'hd': 'True'
        }
        
        try:
            response = requests.get(API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching APOD data for {current_date_str}: {e}")
            continue
        
        # 检查是否是图片
        if data.get('media_type') != 'image':
            print(f"APOD for {current_date_str} is a {data.get('media_type', 'unknown type')}. Skipping.")
            continue

        image_url = data.get('hdurl') or data.get('url')
        title = data.get('title', f'untitled_apod_{current_date_str}')
        
        if not image_url:
            print(f"Image URL not found for {current_date_str}. Skipping.")
            continue

        # 下载
        if download_image(image_url, title, current_date_str):
            downloaded_count += 1
            new_files_downloaded = True
            
    print(f"\nBatch script finished. Total new images downloaded: {downloaded_count}")
    set_action_output(new_files_downloaded)

if __name__ == "__main__":
    main()
