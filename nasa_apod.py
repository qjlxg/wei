import requests
import json
import os
from datetime import datetime
import sys

# --- 配置 ---

# 1. API 基础 URL
API_URL = "https://api.nasa.gov/planetary/apod"

# 2. 目标文件夹的根目录
BASE_OUTPUT_DIR = "nasa_apod_wallpapers"

# 3. 环境变量中的 NASA API KEY 名称
API_KEY_ENV_VAR = "NASA_API_KEY"

# ----------------

def set_action_output(new_files_downloaded):
    """使用 Environment File 输出状态给 GitHub Actions"""
    output_key = "commit_needed"
    output_value = "true" if new_files_downloaded else "false"
    
    # 检查 GITHUB_OUTPUT 环境变量是否存在
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{output_key}={output_value}\n")
    else:
        # 本地测试 Fallback
        print(f"Output for Actions: {output_key}={output_value}") 

def download_image(image_url, title, date):
    """下载图片并保存到目标目录 (YYYY/MM 结构)"""
    
    # 动态构造目录: nasa_apod_wallpapers/YYYY/MM
    year = date[:4]
    month = date[5:7]
    current_output_dir = os.path.join(BASE_OUTPUT_DIR, year, month)
    
    os.makedirs(current_output_dir, exist_ok=True)
    
    # **修复后的代码：正确的 F-string 语法和文件名清理**
    # 构造原始文件名: YYYY-MM-DD_标题.jpg
    title_safe = title.replace(' ', '_').replace('/', '_')
    raw_filename = f"{date}_{title_safe}.jpg"
    
    # 严格移除文件名中所有非法或不必要的字符，确保文件系统兼容性
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
    """主函数 - 获取 NASA APOD 并下载"""
    
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"FATAL: {API_KEY_ENV_VAR} environment variable not set. Please set the Secret to DEMO_KEY.")
        set_action_output(False)
        sys.exit(1)

    params = {
        'api_key': api_key,
        'hd': 'True' # 请求高清版本
    }

    print("Fetching today's APOD data...")
    
    try:
        response = requests.get(API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"Error fetching APOD data: {e}")
        set_action_output(False)
        return
        
    # 检查是否是图片 (APOD 有时是视频或HTML)
    if data.get('media_type') != 'image':
        print(f"Today's APOD is a {data.get('media_type', 'unknown type')}. Skipping download.")
        set_action_output(False)
        return

    # 优先使用高清链接 (hdurl)
    image_url = data.get('hdurl') or data.get('url')
    title = data.get('title', 'untitled_apod')
    date = data.get('date', datetime.now().strftime("%Y-%m-%d"))

    if not image_url:
        print("Image URL not found in APOD data. Skipping.")
        set_action_output(False)
        return

    print(f"APOD Date: {date}, Title: {title}")
    
    # 下载
    new_files_downloaded = download_image(image_url, title, date)
    
    print("Script finished.")
    set_action_output(new_files_downloaded)

if __name__ == "__main__":
    main()
