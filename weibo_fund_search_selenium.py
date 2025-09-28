import requests
from bs4 import BeautifulSoup
import re

def search_weibo_without_login(keyword):
    url = f"https://s.weibo.com/weibo?q={keyword}&xsort=hot"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 解析微博卡片
        cards = soup.select(".card-wrap")
        if not cards:
            print("未找到微博内容，可能需要登录或触发反爬机制")
            return
        
        results = []
        for card in cards:
            weibo_id = card.get("mid", "")
            content = card.select_one(".txt").get_text(strip=True) if card.select_one(".txt") else ""
            time = card.select_one(".from a").get_text(strip=True) if card.select_one(".from a") else ""
            results.append({
                "weibo_id": weibo_id,
                "content": content,
                "time": time
            })
        
        for result in results:
            print(f"微博ID: {result['weibo_id']}\n内容: {result['content']}\n时间: {result['time']}\n{'-'*50}")
        
        # 检查是否有下一页
        next_page = soup.select_one("a.next[href]")
        if next_page:
            print("发现下一页，可继续爬取：", next_page["href"])
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败：{e}")

if __name__ == "__main__":
    keyword = "喜剧之王单口季"
    search_weibo_without_login(keyword)
