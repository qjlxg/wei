import requests
import json
import os
import re
from datetime import datetime

# --- 配置 ---
# 1. API 基础 URL
BASE_URL = "https://earthview.withgoogle.com"

# 2. 修正后的起始 API 点 (替换为已知有效的 API，例如: Mount Fuji)
# 您可以随时从网站随机选择一个替换，格式为: /_api/<slug>-<id>.json
START_API = "/_api/mount-fuji-japan-4927.json"  

# 3. 要下载图片的数量（0 表示所有）
NUM_IMAGES_TO_FETCH = 8

# 4. 目标文件夹的根目录
BASE_OUTPUT_DIR = "google_earthview_wallpapers"

# ----------------

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(image_url, title, id):
    """下载图片并保存到目标目录 (YYYY/MM 结构)"""
    
    # 动态构造目录: google_earthview_wallpapers/YYYY/MM
    now = datetime.now()
    current_output_dir = os.path.join(BASE_OUTPUT_DIR, str(now.year), f"{now.month:02d}")
    
    os.makedirs(current_output_dir, exist_ok=True)
    
    # 清理标题
    safe_title = sanitize_filename(title) if title else f"earthview_{id}"
    
    # 文件名: ID_标题.jpg
    filename = f"{id}_{safe_title}.jpg"
    filepath = os.path.join(current_output_dir, filename)
    
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading {title} (ID: {id}) to {filepath}")
    
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
    """主函数 - 下载 Google Earth View 壁纸"""
    current = START_API
    ids = set()
    downloaded_count = 0
    new_files_downloaded = False
    
    print(f"Attempting to fetch up to {NUM_IMAGES_TO_FETCH if NUM_IMAGES_TO_FETCH > 0 else 'all'} images from Google Earth View.")
    
    while True:
        url = BASE_URL + current
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = json.loads(response.content)
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"Error fetching data from {url}: {e}")
            break
            
        # ... (获取 download_url, image_id, title 逻辑保持不变)
        download_url = data.get("photoUrl")  
        if not download_url:
            download_url = data.get("downloadUrl")
        if not download_url:
            print(f"Skipping image due to missing download URL.")
            continue
            
        image_url = BASE_URL + download_url
        image_id = data.get("id", "unknown")
        title = data.get("slug", data.get("region", "untitled"))  
        
        # ... (去重检查逻辑保持不变)
        if image_id in ids:
            print("Loop detected. Exiting.")
            break
        ids.add(image_id)
        
        # 下载
        if download_image(image_url, title, image_id):
            downloaded_count += 1
            new_files_downloaded = True
        
        # ... (检查下载限制逻辑保持不变)
        if NUM_IMAGES_TO_FETCH > 0 and downloaded_count >= NUM_IMAGES_TO_FETCH:
            print("Reached download limit. Exiting.")
            break
            
        # ... (下一个 API 逻辑保持不变)
        next_api = data.get("nextApi")
        if not next_api:
            print("No more images. Exiting.")
            break
        current = next_api
    
    print(f"Script finished. Total images downloaded: {downloaded_count}")
    
    # 🌟 **核心修复:** 使用 GitHub Actions 推荐的 Environment File 输出
    output_key = "commit_needed"
    output_value = "true" if new_files_downloaded else "false"
    
    # 检查 GITHUB_OUTPUT 变量是否存在（只在 GitHub Actions 环境中存在）
    if os.environ.get("GITHUB_OUTPUT"):
        # 将键值对写入 GITHUB_OUTPUT 文件
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{output_key}={output_value}\n")
    else:
        # Fallback: 在本地运行或非 Actions 环境中，仍使用 print 输出状态
        print(f"Output for Actions: {output_key}={output_value}") 

if __name__ == "__main__":
    main()
