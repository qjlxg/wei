import os
import requests
from bs4 import BeautifulSoup
import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor

# --- 1. 过滤配置 ---
# 广告关键词黑名单：直接丢弃包含这些词的消息
AD_KEYWORDS = [
    "极搜", "JISOU", "精准找到", "搜索引擎", "t.me/jisou",
    "点击加入", "博彩", "开奖", "私推", "联系客服"
]

# 系统消息关键字：直接丢弃这些 Telegram 自动生成的文本
SYSTEM_PATTERNS = [
    "Channel created", 
    "Channel name was changed", 
    "Channel photo updated",
    "Welcome to",
    "👋"
]

# User-Agent 池
UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

# --- 2. 频道列表 (保持完整，不精简) ---
channels = [
    'boombergzh', 'clsvip', 'FinanceNewsDaily', 'gainiantuhua', 'gsxt233', 
    'guanshuitan', 'hejrb233', 'hejrb2333', 'hgclhyyb', 'Jin10Data', 
    'kingkitay', 'metwarn', 'nysbsy', 'ok2tradecurrency', 'pelosi3', 
    'qzdzb', 'reuterszh', 'rsssubscibe', 'tnews365', 'WorldSpotNews', 
    'ywcqdz', 'zaobaocn',
    'BondMarketLive', 'CaixinGlobal', 'ChartLovers', 'CommodityPulse',
    'DeepMacro', 'ForexFactory_News', 'FundFlowWatcher', 'FuturesEdge',
    'Gavekal', 'IceBricks', 'PriceActionCN', 'QuantAnalysis',
    'TradingView_ZH', 'WallStreetNews'
]

def get_channel_content(channel_name):
    # 随机延迟，防止被 Telegram 识别为爬虫导致“未抓取到内容”
    time.sleep(random.uniform(0.5, 1.2))
    
    print(f"[*] 正在抓取: {channel_name}")
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': random.choice(UA_LIST)}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        message_elements = soup.find_all('div', class_='tgme_widget_message')
        if not message_elements:
            return f"## 来源: {channel_name}\n> 该频道当前无法通过 Web 预览或无公开内容。\n\n---\n\n"
    except Exception as e:
        return f"## 来源: {channel_name}\n> 抓取异常: {e}\n\n---\n\n"
    
    content_list = []
    seen_ids = set()
    
    # 提取最近 10 条消息
    for msg in message_elements[-10:]:
        msg_id = msg.get('data-post')
        if msg_id in seen_ids: continue
        seen_ids.add(msg_id)

        text_div = msg.find('div', class_=['tgme_widget_message_text', 'js-message_text'])
        if text_div:
            raw_text = text_div.get_text(separator="\n").strip()
            
            # 过滤 1: 系统通知
            if any(p in raw_text for p in SYSTEM_PATTERNS):
                continue
                
            # 过滤 2: 广告关键词
            if any(word in raw_text for word in AD_KEYWORDS):
                continue
            
            # 过滤 3: 过短或无意义内容 (如单纯一个 emoji)
            if len(raw_text) < 10:
                continue

            content_list.append(f"{raw_text}\n\n---\n\n")
            
    if not content_list:
        return f"## 来源: {channel_name}\n> 暂无有效资讯内容 (已过滤系统信息或广告)。\n\n---\n\n"

    return f"## 来源: {channel_name}\n\n" + "".join(content_list)

def main():
    sh_tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(sh_tz)
    sh_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"任务启动: {sh_time}")
    
    # 线程池并发执行
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(get_channel_content, channels))

    final_output = f"# 汇总\n\n**最后更新: {sh_time}**\n\n"
    final_output += "".join(results)

    # 写入 README
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(final_output)
    
    # 存档
    os.makedirs("history", exist_ok=True)
    with open(f"history/{now.strftime('%Y-%m-%d')}.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n### 抓取时点: {sh_time}\n\n" + final_output)

    # Issue 导出
    with open("issue_body.md", "w", encoding="utf-8") as f:
        f.write(final_output)
    
    print(f"任务结束。")

if __name__ == "__main__":
    main()
