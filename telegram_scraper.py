import os
import requests
from bs4 import BeautifulSoup
import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor

# --- 1. 过滤配置 ---

# 广告关键词黑名单：涵盖了付费频道项目、资源引流及特定话术
AD_KEYWORDS = [
    # 付费项目特征
    "频道收费项目", "频道VIP", "包括内容：", "红宝书", "小作文", "机构观点", 
    "盘中消息通报", "专属股票交流群", "收费群盘中消息同步", "费用：100元/月",
    "VIP资讯", "环球资讯", "机构资讯", "商务合作", "联系客服",
    
    # 资源频道引流原文
    "每日分享B站各类课程", "及其它影视", "软件工具以及羊毛", "千奇百怪有趣的东西", 
    "关注频道 👉", "https://t.me/hezuclub", "极搜", "JISOU",
    
    # 核心游资/大V名单 (用于识别搬运类广告)
    "老樊", "老多", "梅森投研", "格兰投研", "妖股刺客", "麦芽糖", "新生代龙头玩家", 
    "邢者狩猎营", "G界孙悟空", "大师兄擒妖", "超级感悟", "主升真经", "天机短线", 
    "爱尔兰画眉", "红旗大街发哥", "游资混江龙", "徐小明", "天地同力", "情绪流作手C神", 
    "趋势Moo", "逻辑A哥", "复盘哥", "鑫多多", "奶爸只做核心", "钱塘李逍遥", "K神会",
    
    # 营销动作词
    "点击加入", "博彩", "开奖", "私推", "普洱茶", "进群", "扫码", "看评论区"
]

# 系统消息关键字：直接丢弃 Telegram 自动生成的文本
SYSTEM_PATTERNS = [
    "Channel created", "Channel name was changed", "Channel photo updated",
    "Welcome to", "pinned a message", "changed the description", "👋"
]

# 导航与特定后缀：识别并剔除纯导航类消息
NAVIGATION_PATTERNS = [
    "导航 :  频道 | 群组 | VIP服务 | 带货",
    "友情链接", "唯一官方频道", "唯一客服", "自助导航"
]

# 股票相关引流标签
SPAM_TAGS = [
    "#炒股笔记", "#交易记录", "#交易", "#模拟交易", 
    "#轻舟指标", "#股票", "#股市", "#A股"
]

# --- 2. 逻辑验证逻辑 ---
# 建议处理流程：
# 1. 检查是否包含 SYSTEM_PATTERNS -> 丢弃
# 2. 检查是否命中 AD_KEYWORDS (不分大小写) -> 丢弃
# 3. 检查是否命中 NAVIGATION_PATTERNS -> 丢弃


# User-Agent 池
UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

#  2. 频道列表
channels = [
    'metwarn','clsvip', 'FinanceNewsDaily', 'hejrb233', 'hgclhyyb', 'Jin10Data', 'kingkitay','ok2tradecurrency', 
    'pelosi3',  'reuterszh','tnews365', 'WorldSpotNews', 'ywcqdz', 'zaobaocn'
    
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
