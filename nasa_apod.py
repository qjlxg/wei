import requests
import os
import re
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置 ---

# 1. API 基础 URL
API_URL = "https://api.nasa.gov/planetary/apod"

# 2. **批量下载配置：起始日期**
# 格式必须是 YYYY-MM-DD
START_DATE = "1995-06-16"

# 3. 目标文件夹的根目录
BASE_OUTPUT_DIR = "nasa_apod_wallpapers"

# 4. 环境变量中的 NASA API KEY 名称
API_KEY_ENV_VAR = "NASA_API_KEY"

# 5. 【新增】并发配置：最大并行线程数
MAX_WORKERS = 8 # 建议设置为 4 到 8 之间

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
    # 使用更安全的清理方式，只保留字母数字、下划线、点号和短横线
    title_safe = title.replace(' ', '_')
    raw_filename = f"{date}_{title_safe}.jpg"
    
    # 移除文件名中所有非法或不必要的字符
    # 允许的字符：字母数字、_ . -
    safe_filename = re.sub(r'[^\w\.\-]', '', raw_filename)
    filepath = os.path.join(current_output_dir, safe_filename)
    
    if os.path.exists(filepath):
        # print(f"File already exists: {filepath}. Skipping download.")
        return False
        
    print(f"Downloading {title} ({date}) to {filepath}")
    
    try:
        # 增加超时时间，以防大文件下载慢
        img_response = requests.get(image_url, stream=True, timeout=60) 
        img_response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully saved: {filepath}")
        return True
    except requests.RequestException as e:
        print(f"Error downloading image {image_url} ({date}): {e}")
        return False

# 【新增核心函数】：处理指定年份的任务
def process_year(year, api_key):
    """处理指定年份内所有日期的 APOD 下载"""
    
    start_of_year = datetime(year, 1, 1).date()
    end_of_year = datetime(year, 12, 31).date()
    
    # 确保不抓取未来或超过 START_DATE 的数据
    today = datetime.now().date()
    global_start_date_obj = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    
    # 确定当前年份的实际开始日期和结束日期
    actual_start_date = max(start_of_year, global_start_date_obj)
    actual_end_date = min(end_of_year, today)
    
    if actual_start_date > actual_end_date:
        return 0, False
        
    delta = actual_end_date - actual_start_date
    year_downloaded_count = 0
    year_new_files = False
    
    print(f"\n--- Starting concurrent process for Year {year} ({actual_start_date} to {actual_end_date}) ---")

    for i in range(delta.days + 1):
        current_date_obj = actual_start_date + timedelta(days=i)
        current_date_str = current_date_obj.strftime("%Y-%m-%d")
        
        params = {
            'api_key': api_key,
            'date': current_date_str,
            'hd': 'True'
        }
        
        try:
            # 缩短 API 请求超时时间
            response = requests.get(API_URL, params=params, timeout=10) 
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            # 打印 API 错误，但继续下一天
            print(f"API Error fetching APOD data for {current_date_str}: {e}")
            continue
        
        # 检查是否是图片
        if data.get('media_type') != 'image':
            # print(f"APOD for {current_date_str} is a {data.get('media_type', 'unknown type')}. Skipping.")
            continue

        # 检查是否是视频，如果是视频，尝试获取其缩略图或使用原链接
        image_url = data.get('hdurl') or data.get('url')
        
        # NASA APOD 有时返回 YouTube 链接，这不适合作为壁纸下载
        if image_url and 'youtube' in image_url:
            print(f"APOD for {current_date_str} is a video. Skipping.")
            continue
            
        title = data.get('title', f'untitled_apod_{current_date_str}')
        
        if not image_url:
            print(f"Image URL not found for {current_date_str}. Skipping.")
            continue

        # 下载
        if download_image(image_url, title, current_date_str):
            year_downloaded_count += 1
            year_new_files = True
            
    print(f"--- Finished Year {year}. New files: {year_downloaded_count} ---")
    return year_downloaded_count, year_new_files

def main():
    """主函数 - 并发获取 APOD 并下载"""
    
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"FATAL: {API_KEY_ENV_VAR} environment variable not set. Please set the Secret (using a proper key or DEMO_KEY).")
        set_action_output(False)
        sys.exit(1)

    try:
        start_date_obj = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    except ValueError:
        print("FATAL: START_DATE format is incorrect. Must be YYYY-MM-DD.")
        set_action_output(False)
        sys.exit(1)
        
    end_date_obj = datetime.now().date()
    
    if start_date_obj > end_date_obj:
        print("Start date is in the future. Exiting.")
        set_action_output(False)
        return

    # 1. 确定需要处理的年份范围
    start_year = start_date_obj.year
    end_year = end_date_obj.year
    years_to_process = list(range(start_year, end_year + 1))
    
    print(f"Starting concurrent batch download from {START_DATE} to {end_date_obj.strftime('%Y-%m-%d')}.")
    print(f"Processing {len(years_to_process)} years concurrently using {MAX_WORKERS} threads.")
    
    total_downloaded_count = 0
    total_new_files_downloaded = False

    # 2. 使用 ThreadPoolExecutor 并发处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有年份任务
        future_to_year = {executor.submit(process_year, year, api_key): year for year in years_to_process}
        
        # 收集结果
        for future in as_completed(future_to_year):
            year = future_to_year[future]
            try:
                downloaded_count, new_files_status = future.result()
                total_downloaded_count += downloaded_count
                if new_files_status:
                    total_new_files_downloaded = True
            except Exception as exc:
                print(f'Year {year} generated an exception: {exc}')

    print(f"\nBatch script finished. Total new images downloaded: {total_downloaded_count}")
    set_action_output(total_new_files_downloaded)

if __name__ == "__main__":
    main()