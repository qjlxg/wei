import requests
import os
import re
from datetime import datetime
import random 

# --- 配置 ---

# 1. Gist URL 配置 (用于动态获取 ID 列表)
GIST_URL = "https://gist.githubusercontent.com/jzc/2d353c7e0815f6059642c9445919e7de/raw/187f6beacd3abf0fad991c0b7e89c4a2635b15dd/urls.txt"

# 2. 图片托管基础 URL
IMAGE_BASE_URL = "https://www.gstatic.com/prettyearth/assets/full/"

# 3. 要下载图片的数量（0 表示所有，如果设为 8，则每次运行下载 8 张不同的图片）
NUM_IMAGES_TO_FETCH = 8

# 4. 目标文件夹的根目录
BASE_OUTPUT_DIR = "google_earthview_wallpapers"

# ----------------

def fetch_and_extract_ids(url):
    """从 Gist URL 获取内容，并提取所有 ID"""
    print(f"Fetching IDs from: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() # 检查 4xx/5xx 错误
        
        # 使用正则表达式查找 /full/ 后跟数字，直到 .jpg
        content = response.text
        ids = re.findall(r'/full/(\d+)\.jpg', content) 
        
        # 返回去重后的 ID 列表
        unique_ids = list(set(ids))
        print(f"Successfully fetched {len(unique_ids)} unique IDs.")
        return unique_ids
        
    except requests.RequestException as e:
        print(f"Error fetching Gist content: {e}")
        return []

def sanitize_filename(filename):
    """清理文件名中的非法字符 (不再严格需要，但保留以防未来扩展)"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(image_url, id):
    """下载图片并保存到目标目录 (YYYY/MM 结构)"""
    
    # 动态构造目录: google_earthview_wallpapers/YYYY/MM
    now = datetime.now()
    current_output_dir = os.path.join(BASE_OUTPUT_DIR, str(now.year), f"{now.month:02d}")
    
    os.makedirs(current_output_dir, exist_ok=True)
    
    # 文件名: ID.jpg
    filename = f"{id}.jpg"
    filepath = os.path.join(current_output_dir, filename)
    
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading image (ID: {id}) to {filepath}")
    
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
    """主函数 - 循环下载 Google Earth View 壁纸"""
    
    # 动态获取 ID 列表
    all_image_ids = fetch_and_extract_ids(GIST_URL)
    
    if not all_image_ids:
        print("Fatal: Could not fetch image IDs. Exiting.")
        set_action_output(False)
        return

    downloaded_count = 0
    new_files_downloaded = False
    
    # 随机化 ID 列表，确保每次运行下载不同的图片
    random.shuffle(all_image_ids)
    
    # 根据限制裁剪列表
    ids_to_fetch = all_image_ids
    if NUM_IMAGES_TO_FETCH > 0:
        ids_to_fetch = all_image_ids[:NUM_IMAGES_TO_FETCH]
    
    print(f"Attempting to fetch {len(ids_to_fetch)} images from Gstatic server.")
    
    for image_id in ids_to_fetch:
        # 构造新的下载 URL
        image_url = f"{IMAGE_BASE_URL}{image_id}.jpg"
        
        # 下载
        if download_image(image_url, image_id):
            downloaded_count += 1
            new_files_downloaded = True
            
    print(f"Script finished. Total images downloaded: {downloaded_count}")
    
    # 将最终状态传递给 GitHub Actions (Environment File 修复)
    set_action_output(new_files_downloaded)

def set_action_output(new_files_downloaded):
    """使用 Environment File 输出状态给 GitHub Actions"""
    output_key = "commit_needed"
    output_value = "true" if new_files_downloaded else "false"
    
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{output_key}={output_value}\n")
    else:
        # 本地测试 Fallback
        print(f"Output for Actions: {output_key}={output_value}") 

if __name__ == "__main__":
    main()
