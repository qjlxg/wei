import requests
from datetime import datetime
import pytz
import json
import os

# 设置时区为上海
SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')

def fetch_and_save_wiki_picture():
    """
    获取维基百科每日图片并保存到带有上海时区时间戳的文件中。
    """
    try:
        # 获取当前上海时间
        now_shanghai = datetime.now(SHANGHAI_TZ)
        
        # 构造API请求URL以获取维基百科每日图片 (使用 /page/media-list)
        # 注意：这只是一个示例。维基百科“每日图片”的最佳获取方法是使用MediaWiki API
        # 这里的示例是获取主页上的每日图片，通常在 'Featured picture' 模块中。
        # 实际操作中，您可能需要更复杂的解析或者使用专门的API。
        
        # 示例：获取特定日期 (当天) 的每日图片信息
        # 维基百科每日图片模板名称通常是 Template:Potd/YYYY-MM-DD
        date_str = now_shanghai.strftime('%Y-%m-%d')
        template_name = f'Template:Potd/{date_str}'
        
        API_ENDPOINT = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "titles": template_name,
            "iiprop": "url|extmetadata",
            "generator": "templates",
            "gtprop": "title",
            "gttitle": "Main_Page",
            "gtnamespace": "10", # Template namespace
            "gtlimit": "1" # Limit to 1 result
        }

        # 实际上，维基百科每日图片通常直接使用一个固定的模板，我们尝试直接获取其内容
        params = {
            "action": "query",
            "format": "json",
            "prop": "revisions",
            "titles": f"Template:Potd/{date_str}",
            "rvprop": "content",
            "rvlimit": "1",
            "rvcontentformat": "text/x-wiki"
        }
        
        response = requests.get(API_ENDPOINT, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 尝试解析内容 (这可能因维基模板结构而异，以下是一个通用尝试)
        page_id = next(iter(data['query']['pages']))
        content = data['query']['pages'][page_id]['revisions'][0]['*']
        
        # 从内容中提取文件名（通常在 {{1/Potd/...}} 或 [[File:...] 中）
        # 这是一个简化的示例，仅将整个模板内容作为结果
        result_content = f"--- Wikipedia Picture of the Day for {date_str} ---\n\n"
        result_content += content
        
        # 构造文件名和路径
        year = now_shanghai.strftime('%Y')
        month = now_shanghai.strftime('%m')
        timestamp_filename = now_shanghai.strftime('%Y-%m-%d-%H-%M-%S') + '.txt'
        
        # 目标目录: YYYY/MM
        target_dir = os.path.join(year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        # 目标文件路径
        file_path = os.path.join(target_dir, timestamp_filename)
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(result_content)
        
        print(f"✅ 成功获取维基图片信息并保存到: {file_path}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 发生网络请求错误: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 发生其他错误: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_save_wiki_picture()
