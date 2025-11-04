import requests
import datetime
import os
import re
from bs4 import BeautifulSoup  # 添加 BeautifulSoup 用于网页刮取
# --- 配置 ---
# 1. 稳定数据源 (用于获取可靠的 hdate/utctime)
BING_API_URL_DATA = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=en-US"
# 2. 中文标题源 (用于获取中文标题)
BING_API_URL_TITLE = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={}&n={}&mkt=zh-CN"
# 要下载图片的数量（今天 + 历史）
NUM_IMAGES_TO_FETCH = 8
# 图片分辨率 (例如: 1920x1080)
RESOLUTION = "1920x1080"
# 目标文件夹
OUTPUT_DIR = "bing_images"
# 上海时区
SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
# 新增：其他来源的配置
OTHER_SOURCES = {
    "nasa_apod": {
        "api_url": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY&count={}",
        "type": "api",
        "key": "hdurl",  # 图片URL键
        "title_key": "title",
        "date_key": "date"
    },
    "nat_geo": {
        "api_url": "https://natgeoapi.herokuapp.com/api/dailyphoto",
        "type": "api",
        "key": "items[0].image.url",  # 根据unofficial API
        "title_key": "items[0].title"
    },
    "unsplash": {
        "api_url": "https://api.unsplash.com/photos/random?client_id=YOUR_UNSPLASH_KEY&count={}",
        "type": "api",
        "key": "urls.full",
        "title_key": "alt_description",
        "note": "需要替换 YOUR_UNSPLASH_KEY 为你的API密钥 (从 https://unsplash.com/developers 获取)"
    },
    "pexels": {
        "api_url": "https://api.pexels.com/v1/curated?per_page={}",
        "type": "api",
        "headers": {"Authorization": "YOUR_PEXELS_KEY"},
        "key": "src.original",
        "title_key": "photographer",
        "note": "需要替换 YOUR_PEXELS_KEY 为你的API密钥 (从 https://www.pexels.com/api/ 获取)"
    },
    "wallhaven": {
        "url": "https://wallhaven.cc/toplist?sorting=date_added&order=desc",
        "type": "scrape",
        "img_selector": "figure a.preview img"  # 示例选择器，可能需调整
    },
    "guardian": {
        "url": "https://www.theguardian.com/news/series/ten-best-photographs-of-the-day",
        "type": "scrape",
        "img_selector": "img[src^='https://i.guim.co.uk']"  # 示例
    },
    "twistedsifter": {
        "url": "https://twistedsifter.com/category/picture-of-the-day/",
        "type": "scrape",
        "img_selector": "article img.wp-image"  # 示例
    },
    "voa": {
        "url": "https://www.voanews.com/p/5341.html",
        "type": "scrape",
        "img_selector": "div.photo img"  # 示例
    },
    "popphoto": {
        "url": "https://www.popphoto.com/category/photo-of-the-day/",
        "type": "scrape",
        "img_selector": "img[srcset]"  # 示例
    }
}
# ----------------
def get_bing_data(api_url, index, count):
    """从指定的 Bing API URL 获取图片数据"""
    url = api_url.format(index, count)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get('images', [])
    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return []
def get_chinese_titles(images_data_en):
    """获取中文市场（zh-CN）的图片标题，用于匹配英文数据"""
    print("Fetching Chinese titles from zh-CN market...")
    images_data_zh = get_bing_data(BING_API_URL_TITLE, index=0, count=NUM_IMAGES_TO_FETCH)
   
    zh_titles = {}
    for img_zh in images_data_zh:
        # 使用 urlbase 作为唯一键来匹配不同市场的图片
        urlbase = img_zh.get('urlbase')
        title = img_zh.get('copyright')
        if urlbase and title:
            zh_titles[urlbase] = title
           
    return zh_titles
def sanitize_filename(filename):
    """清理文件名中的非法字符，保留原始标题主体"""
    # 移除文件路径中的非法字符（例如 \ / : * ? " < > |）
    safe_name = re.sub(r'[\\/:*?"<>|]', ' ', filename)
    # 将多个空格替换为一个下划线
    safe_name = re.sub(r'\s+', '_', safe_name).strip('_')
    return safe_name
def download_image(base_url, start_date, title):
    """下载图片并保存到目标目录"""
    image_url = f"https://www.bing.com{base_url}_{RESOLUTION}.jpg"
   
    # 构造目录: bing_images/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, year, month)
    os.makedirs(target_dir, exist_ok=True)
   
    # 清理标题
    safe_title = sanitize_filename(title)
   
    # 文件名: 年月日_时分秒_清理后的原始标题.jpg
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
       
    print(f"Downloading {title} to {filepath}")
   
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
# 新增函数：从其他来源获取数据
def get_source_data(source_name, config):
    """从指定来源获取图片数据"""
    if config['type'] == 'api':
        url = config['api_url'].format(NUM_IMAGES_TO_FETCH)
        headers = config.get('headers', {})
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            # 根据键提取图片列表
            if source_name == 'nat_geo':
                return [data] if 'items' not in data else data['items']  # 调整为列表
            elif source_name == 'unsplash':
                return data  # 列表
            elif source_name == 'pexels':
                return data['photos']
            elif source_name == 'nasa_apod':
                return data
            else:
                return []
        except Exception as e:
            print(f"Error fetching {source_name}: {e}")
            return []
    elif config['type'] == 'scrape':
        try:
            response = requests.get(config['url'], timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            imgs = soup.select(config['img_selector'])[:NUM_IMAGES_TO_FETCH]
            images = []
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                title = img.get('alt') or img.get('title') or f"{source_name}_image"
                images.append({'url': src, 'title': title, 'date': datetime.date.today().strftime('%Y%m%d')})
            return images
        except Exception as e:
            print(f"Error scraping {source_name}: {e}")
            return []
    return []
# 新增函数：下载其他来源的图片
def download_source_image(image_url, start_date, title, source_name):
    """下载其他来源的图片"""
    # 构造目录: OUTPUT_DIR/source_name/年/月
    year = start_date.strftime('%Y')
    month = start_date.strftime('%m')
    target_dir = os.path.join(OUTPUT_DIR, source_name, year, month)
    os.makedirs(target_dir, exist_ok=True)
   
    # 清理标题
    safe_title = sanitize_filename(title)
   
    # 文件名: 年月日_时分秒_清理后的原始标题.jpg
    timestamp = start_date.strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_title}.jpg"
    filepath = os.path.join(target_dir, filename)
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}. Skipping download.")
        return False
       
    print(f"Downloading {title} from {source_name} to {filepath}")
   
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
    """主函数"""
   
    print(f"Attempting to fetch {NUM_IMAGES_TO_FETCH} images using the stable en-US market...")
    images_en = get_bing_data(BING_API_URL_DATA, index=0, count=NUM_IMAGES_TO_FETCH)
   
    if not images_en:
        print("Failed to fetch any image data from the stable market. Exiting.")
        return
    # 获取中文标题映射
    zh_titles_map = get_chinese_titles(images_en)
   
    downloaded_count = 0
   
    for img_data in images_en:
        hdate_str = img_data.get('startdate') # YYYYMMDD
        utctime_str = img_data.get('fullstartdate') # YYYYMMDDHHMM (可能缺失)
        urlbase = img_data.get('urlbase')
       
        if not hdate_str or not urlbase:
            print(f"Skipping image due to missing critical data (hdate/urlbase).")
            continue
           
        # 优先使用中文标题，否则使用英文标题
        final_title = zh_titles_map.get(urlbase, img_data.get('copyright', 'bing_wallpaper_en'))
        try:
            shanghai_datetime = None
           
            if utctime_str:
                # 方案 A: 使用 utctime
                utc_datetime = datetime.datetime.strptime(utctime_str, '%Y%m%d%H%M').replace(tzinfo=datetime.timezone.utc)
                shanghai_datetime = utc_datetime.astimezone(SHANGHAI_TZ)
            else:
                # 方案 B: utctime 缺失，使用 hdate 和上海午夜时间 (00:00:00)
                print(f"Warning: utctime missing for {final_title}. Using hdate with 00:00:00 Shanghai time.")
                shanghai_date = datetime.datetime.strptime(hdate_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
           
            # 下载图片
            if download_image(urlbase, shanghai_datetime, final_title):
                downloaded_count += 1
               
        except ValueError as e:
            print(f"Error parsing date/time for image {final_title}: {e}")
       
    print(f"Script finished. Total new images downloaded from Bing: {downloaded_count}")
    
    # 新增：下载其他来源
    for source_name, config in OTHER_SOURCES.items():
        print(f"\nFetching {NUM_IMAGES_TO_FETCH} images from {source_name}...")
        if 'note' in config:
            print(f"Note: {config['note']}")
        images = get_source_data(source_name, config)
        source_downloaded = 0
        for img in images:
            image_url = img.get(config.get('key', 'url'))
            title = img.get(config.get('title_key', 'title'), f"{source_name}_image")
            date_str = img.get(config.get('date_key', 'date'), datetime.date.today().strftime('%Y%m%d'))
            try:
                shanghai_date = datetime.datetime.strptime(date_str, '%Y-%m-%d') if '-' in date_str else datetime.datetime.strptime(date_str, '%Y%m%d')
                shanghai_datetime = SHANGHAI_TZ.localize(shanghai_date)
            except:
                shanghai_datetime = datetime.datetime.now(SHANGHAI_TZ)
            if download_source_image(image_url, shanghai_datetime, title, source_name):
                source_downloaded += 1
        print(f"Total new images downloaded from {source_name}: {source_downloaded}")
if __name__ == "__main__":
    main()
