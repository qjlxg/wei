import requests
import json
import time
from weibo_scraper import get_weibo_tweets

# 搜索关键词
keyword = "基金"
search_api = "https://m.weibo.cn/api/container/getIndex?type=wb&queryVal={}&containerid=100103type=1&q={}"

# Headers模拟移动端浏览器
headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Accept": "application/json, text/plain, */*"
}

def fetch_container_id(keyword):
    """获取搜索关键词的containerid"""
    url = search_api.format(keyword, keyword)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') and data.get('data', {}).get('cards'):
                # 从cards中提取containerid（通常在card_group中）
                for card in data['data']['cards']:
                    if 'card_group' in card:
                        for item in card['card_group']:
                            if item.get('containerid'):
                                return item['containerid']
            print("No containerid found for keyword:", keyword)
            return None
        else:
            print(f"Failed to fetch search API: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching containerid: {e}")
        return None

def fetch_tweets(container_id, max_pages=5):
    """获取搜索结果的帖子文本内容"""
    tweets = []
    for page in range(1, max_pages + 1):
        try:
            for tweet in get_weibo_tweets(tweet_container_id=container_id, pages=page):
                # 仅提取文本内容，忽略图片/视频
                text = tweet.get('text', '').strip()
                if text:  # 确保文本不为空
                    tweets.append({
                        "user": tweet['user']['screen_name'],
                        "text": text,
                        "date": tweet['created_at'],
                        "url": f"https://m.weibo.cn/status/{tweet['bid']}"
                    })
            print(f"Processed page {page}")
            time.sleep(2)  # 避免触发反爬
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
    return tweets

def main():
    # 获取containerid
    container_id = fetch_container_id(keyword)
    if not container_id:
        print("Cannot proceed without containerid.")
        return

    # 获取帖子文本
    tweets = fetch_tweets(container_id, max_pages=5)  # 可调整页数

    # 保存结果到JSON
    output_file = 'fund_tweets.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tweets, f, ensure_ascii=False, indent=4)
    print(f"Extracted {len(tweets)} posts. Saved to {output_file}")

if __name__ == "__main__":
    main()
