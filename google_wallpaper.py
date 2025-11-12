import requests
import json
import os
import re

# --- 配置 ---
# 1. API 基础 URL
BASE_URL = "https://earthview.withgoogle.com"

# 2. 起始 API 点（从一个已知图像开始，可从网站随机选一个替换）
START_API = "/_api/lipie-lubaczow-county-poland-1893.json"  # 示例起始点

# 3. 要下载图片的数量（0 表示所有）
NUM_IMAGES_TO_FETCH = 8

# 4. 图片分辨率（Earth View 默认高清，无需指定）

# 5. 目标文件夹
OUTPUT_DIR = "google_earthview_wallpapers"

# ----------------

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(image_url, title, id):
    """下载图片并保存到目标目录"""
    # 构造目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
  
    # 清理标题
    safe_title = sanitize_filename(title) if title else f"earthview_{id}"
  
    # 文件名: ID_标题.jpg
    filename = f"{id}_{safe_title}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)
   
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
        download_url = data.get("photoUrl")  # 实际是 /download/ID.jpg，但网站使用 photoUrl 为高清图像
        if not download_url:
            download_url = data.get("downloadUrl")
        if not download_url:
            print(f"Skipping image due to missing download URL.")
            continue
      
        image_url = BASE_URL + download_url
        image_id = data.get("id", "unknown")
        title = data.get("slug", data.get("region", "untitled"))  # 使用 slug 或 region 作为标题
      
        # 去重检查
        if image_id in ids:
            print("Loop detected. Exiting.")
            break
        ids.add(image_id)
      
        # 下载
        if download_image(image_url, title, image_id):
            downloaded_count += 1
      
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

if __name__ == "__main__":
    main()