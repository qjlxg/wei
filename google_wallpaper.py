import requests
import json
import os
import re
from datetime import datetime

# --- 配置 ---
# 1. API 基础 URL
BASE_URL = "https://earthview.withgoogle.com"

# 2. 初始硬编码 API 点 (如果失效，脚本会尝试自动获取一个新的)
START_API = "/_api/mount-fuji-japan-4927.json" 

# 3. 随机 API 终点（用于动态发现，如果硬编码起点失效）
RANDOM_API = "/random.json" 

# 4. 要下载图片的数量（0 表示所有）
NUM_IMAGES_TO_FETCH = 8

# 5. 目标文件夹的根目录
BASE_OUTPUT_DIR = "google_earthview_wallpapers"

# ----------------

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def get_valid_start_api(initial_api):
    """
    尝试验证初始 API 是否有效。如果失效，则尝试从 /random.json 获取一个新的 API 路径。
    返回: 有效的 API 路径字符串 或 None
    """
    api_to_check = initial_api
    
    # 第一次尝试：检查硬编码的 API
    try:
        response = requests.head(BASE_URL + api_to_check, timeout=5)
        if response.status_code == 200:
            print(f"Found valid starting API: {api_to_check}")
            return api_to_check
    except requests.RequestException:
        pass  # 忽略错误，继续尝试随机 API

    print(f"Initial API {initial_api} failed. Attempting to get random API...")

    # 第二次尝试：从 /random.json 获取一个新的 API
    try:
        random_url = BASE_URL + RANDOM_API
        # 注意: /random.json 实际上会返回一个 JSON，其中包含 nextApi 字段
        response = requests.get(random_url, timeout=10)
        response.raise_for_status()
        data = json.loads(response.content)
        
        # 网站的 /random.json 返回的 JSON 结构通常包含 nextApi 或 selfApi
        new_api = data.get("nextApi") or data.get("selfApi")
        
        if new_api and new_api.startswith("/_api/"):
            print(f"Successfully retrieved new starting API: {new_api}")
            return new_api
            
    except (requests.RequestException, json.JSONDecodeError, AttributeError) as e:
        print(f"Error getting random API: {e}")
        return None
        
    return None

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
    
    # **核心改进点: 获取一个有效的起始 API**
    start_api_path = get_valid_start_api(START_API)
    if not start_api_path:
        print("Fatal: Could not find a valid starting API point. Exiting.")
        # 即使失败，也需要输出状态给 Actions
        set_action_output(False)
        return
        
    current = start_api_path
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
            
        # 获取下载 URL
        download_url = data.get("photoUrl")  
        if not download_url:
            download_url = data.get("downloadUrl")
        if not download_url:
            print(f"Skipping image due to missing download URL.")
            continue
            
        image_url = BASE_URL + download_url
        image_id = data.get("id", "unknown")
        title = data.get("slug", data.get("region", "untitled"))  
        
        # 去重检查
        if image_id in ids:
            print("Loop detected. Exiting.")
            break
        ids.add(image_id)
        
        # 下载
        if download_image(image_url, title, image_id):
            downloaded_count += 1
            new_files_downloaded = True
        
        # 检查下载限制
        if NUM_IMAGES_TO_FETCH > 0 and downloaded_count >= NUM_IMAGES_TO_FETCH:
            print("Reached download limit. Exiting.")
            break
            
        # 下一个 API
        next_api = data.get("nextApi")
        if not next_api:
            print("No more images. Exiting.")
            break
        current = next_api
    
    print(f"Script finished. Total images downloaded: {downloaded_count}")
    
    # 将最终状态传递给 GitHub Actions
    set_action_output(new_files_downloaded)

def set_action_output(new_files_downloaded):
    """使用 Environment File 输出状态给 GitHub Actions"""
    output_key = "commit_needed"
    output_value = "true" if new_files_downloaded else "false"
    
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{output_key}={output_value}\n")
    else:
        # Fallback for local testing
        print(f"Output for Actions: {output_key}={output_value}") 

if __name__ == "__main__":
    main()
