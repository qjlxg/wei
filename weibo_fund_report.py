import requests
from bs4 import BeautifulSoup
import json
import time

# 搜索关键词
keyword = "基金"
search_url = f"https://s.weibo.com/weibo?q={keyword}"

# Headers模拟浏览器
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    # 如果需要登录，添加Cookie: "Cookie": "your_cookie_here"
}

def fetch_search_page(url):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch search page: {response.status_code}")
        return None

def extract_post_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    posts = soup.find_all('div', class_='card-wrap')  # 假设帖子在card-wrap中
    links = []
    for post in posts:
        link_tag = post.find('a', href=True)  # 提取帖子链接
        if link_tag and 'weibo.com' in link_tag['href']:
            links.append("https:" + link_tag['href'] if link_tag['href'].startswith('//') else link_tag['href'])
    return links

def extract_post_content(url):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # 提取用户名
        user_name = soup.find('a', class_='name')  # 调整class根据HTML
        user_name = user_name.text.strip() if user_name else "Unknown"
        
        # 提取帖子文本
        text = soup.find('p', class_='txt')  # 调整class
        text = text.text.strip() if text else "No text"
        
        # 提取日期
        date = soup.find('a', class_='from')  # 调整
        date = date.text.strip() if date else "Unknown date"
        
        # 提取媒体（图片/视频描述）
        media = soup.find_all('img', src=True)
        media_desc = [img.get('alt', 'No desc') for img in media if 'sinajs.cn' in img['src']]
        
        return {
            "user": user_name,
            "text": text,
            "date": date,
            "media": media_desc,
            "url": url
        }
    else:
        print(f"Failed to fetch post: {url}")
        return None

def main():
    html = fetch_search_page(search_url)
    if not html:
        return
    
    links = extract_post_links(html)
    results = []
    
    for link in links:
        content = extract_post_content(link)
        if content:
            results.append(content)
        time.sleep(2)  # 避免频繁请求被封
    
    # 输出结果到JSON文件
    with open('weibo_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"Extracted {len(results)} posts. Saved to weibo_results.json")

if __name__ == "__main__":
    main()
