from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import time

# 搜索关键词（URL编码）
keyword = "基金"
search_url = f"https://s.weibo.com/weibo?q={keyword}"

def setup_driver():
    """设置无头Chrome驱动"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(options=chrome_options)  # 需ChromeDriver在PATH或用webdriver-manager
    return driver

def extract_texts_from_search(driver, max_pages=1):
    """从搜索页面提取帖子文本"""
    tweets = []
    wait = WebDriverWait(driver, 10)

    for page in range(1, max_pages + 1):
        # 加载页面
        driver.get(search_url + f"&page={page}")
        time.sleep(3)  # 等待加载

        # 等待帖子元素出现（基于提供的HTML样本）
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "card-wrap")))
        except:
            print(f"Page {page} failed to load posts.")
            continue

        # 解析HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cards = soup.find_all('div', class_='card-wrap')

        for card in cards:
            # 提取用户名
            user_elem = card.find('a', class_='name')
            user = user_elem.text.strip() if user_elem else "Unknown"

            # 提取帖子文本（优先全文本，如果隐藏则展开）
            text_elem = card.find('p', {'node-type': 'feed_list_content_full'}) or card.find('p', class_='txt')
            text = text_elem.text.strip() if text_elem else "No text"

            # 提取日期
            date_elem = card.find('a', class_='from')  # 或从time标签
            date = date_elem.text.strip() if date_elem else "Unknown date"

            # 提取帖子链接
            link_elem = card.find('a', href=True)
            link = link_elem['href'] if link_elem and 'weibo.com' in link_elem['href'] else search_url

            if text:
                tweets.append({
                    "user": user,
                    "text": text,
                    "date": date,
                    "url": link
                })

        print(f"Processed page {page}, found {len(cards)} cards")
        time.sleep(2)  # 反爬延时

    return tweets

def main():
    driver = setup_driver()
    try:
        tweets = extract_texts_from_search(driver, max_pages=3)  # 调整页数

        # 保存结果
        output_file = 'fund_tweets.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tweets, f, ensure_ascii=False, indent=4)
        print(f"Extracted {len(tweets)} posts. Saved to {output_file}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
