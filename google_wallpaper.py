import requests
import json
import os
import re
from datetime import datetime
import random # 新增：用于打乱 ID 列表

# --- 配置 ---

# 1. 图像 ID 列表（从 Gist 提取，200+ 个）
# 注意：列表应保持在文件顶部，便于维护
IMAGE_IDS = [
    "1893", "5078", "6587", "6256", "1574", "1779", "7012", "6283", "1617", "2212", 
    "1545", "2195", "1946", "1565", "1087", "2259", "5423", "6153", "1105", "1064", 
    "2274", "1860", "1902", "1904", "5484", "2011", "6443", "1394", "1527", "1652", 
    "1728", "1730", "1374", "5984", "6441", "6311", "1049", "6204", "2001", "1986", 
    "5529", "2062", "1280", "2068", "5945", "1077", "5479", "6387", "1582", "6102", 
    "1540", "1267", "5577", "1066", "6262", "7013", "1423", "1839", "6069", "6346", 
    "5761", "2413", "2041", "1381", "6565", "1135", "1787", "6208", "1501", "2280", 
    "2131", "1399", "1161", "1385", "5052", "1832", "1172", "6231", "1131", "1506", 
    "2091", "2021", "2051", "5862", "2403", "1398", "2048", "1816", "2058", "5770", 
    "1353", "6025", "6374", "1774", "6136", "1071", "2167", "2416", "5334", "1785", 
    "5105", "1811", "5237", "2410", "2329", "1698", "1516", "5082", "2272", "5829", 
    "5228", "6436", "1292", "5480", "1763", "5007", "6141", "5016", "2303", "1987", 
    "1230", "1057", "1197", "5626", "2034", "2295", "5073", "1775", "2045", "1955", 
    "2407", "1845", "2156", "5536", "6170", "1964", "1646", "1251", "6137", "1669", 
    "1067", "1427", "2081", "5636", "1687", "5255", "2228", "5689", "6234", "1960", 
    "6120", "6347", "5338", "1538", "2260", "5167", "1909", "1550", "2426", "1885", 
    "6059", "1630", "2318", "6065", "6205", "2292", "1268", "5741", "1639", "5012", 
    "5822", "6229", "2411", "1894", "2052", "6121", "1006", "6589", "5836", "6341", 
    "1738", "5941", "6202", "6213", "2159", "2443", "1359", "1084", "5676", "5612", 
    "2388", "2116", "1128", "2231", "1560", "1139", "6079", "1098", "1883", "1512", 
    "1127", "2360", "7023", "1255", "5502", "6183", "7009", "5588", "1684", "1048", 
    "6160", "1771", "2264", "1920", "6325", "6320", "1796", "5511", "7017", "1713", 
    "1543", "2294", "6465", "1664", "6358", "5053", "1138", "2377", "6045"
]

# 2. 图片托管基础 URL (新的静态 URL)
IMAGE_BASE_URL = "https://www.gstatic.com/prettyearth/assets/full/"

# 3. 要下载图片的数量（从列表中选取前 N 个）
NUM_IMAGES_TO_FETCH = 8

# 4. 目标文件夹的根目录
BASE_OUTPUT_DIR = "google_earthview_wallpapers"

# ----------------

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    # 由于不再有 title/slug，此函数不再严格需要，但保留以防未来使用
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name

def download_image(image_url, id):
    """下载图片并保存到目标目录 (YYYY/MM 结构)"""
    
    # 动态构造目录: google_earthview_wallpapers/YYYY/MM
    now = datetime.now()
    current_output_dir = os.path.join(BASE_OUTPUT_DIR, str(now.year), f"{now.month:02d}")
    
    os.makedirs(current_output_dir, exist_ok=True)
    
    # 文件名: ID.jpg (因为没有标题信息)
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
    
    downloaded_count = 0
    new_files_downloaded = False
    
    # 随机化 ID 列表，确保每次运行下载不同的图片
    ids_to_fetch = IMAGE_IDS[:]
    random.shuffle(ids_to_fetch)
    
    # 根据限制裁剪列表
    if NUM_IMAGES_TO_FETCH > 0:
        ids_to_fetch = ids_to_fetch[:NUM_IMAGES_TO_FETCH]
    
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
        print(f"Output for Actions: {output_key}={output_value}") 

if __name__ == "__main__":
    main()
