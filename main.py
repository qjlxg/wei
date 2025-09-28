import os
import time
import random
import datetime

# 微博数据抓取库 (weibo-scraper)
# 注意：该库的关键词搜索API文档不明确，此处的导入为占位。
# 您需要在 search_weibo_keyword 函数中集成真实的搜索逻辑。
try:
    # 尝试导入 weibo_scraper 库，用于提示依赖已安装
    # from weibo_scraper import search_posts_by_keyword as actual_search_api
    pass 
except ImportError:
    print("Warning: The 'weibo-scraper' library is not installed or the import path is incorrect.")


def classify_tweet(content: str) -> str:
    """
    根据微博内容自动将其分类到三个主题之一。
    
    Args:
        content: 微博的文本内容。
        
    Returns:
        分类的标题字符串。
    """
    # 关键词统一转为小写，以进行不区分大小写的匹配
    content_lower = content.lower()

    # 1. 实盘、买卖与交易记录
    # 重点关注操作性、数字、账户相关的词汇
    trading_keywords = ["实盘", "买卖", "记录", "持仓", "调仓", "交易", "清仓", "加仓", "做t", "收益", "账户"]
    if any(k in content_lower for k in trading_keywords):
        return "📊 个人实盘、买卖与交易记录"

    # 2. 专业分析、政策与宏观影响
    # 重点关注分析性、官方、经济学术语
    analysis_keywords = ["政策", "法规", "宏观", "微观", "国际", "国内", "影响", "分析", "央行", "报告", "经济"]
    if any(k in content_lower for k in analysis_keywords):
        return "📰 专业分析、政策与宏观影响"

    # 3. 经验、心得与体会分享
    # 重点关注个人感受、建议、哲学类的词汇
    experience_keywords = ["心得", "经验", "体会", "分享", "建议", "思考", "感受", "理念", "投资哲学"]
    if any(k in content_lower for k in experience_keywords):
        return "🧠 经验、心得与体会分享"

    # 默认分类
    return "🤔 其他讨论/未分类"


def mock_weibo_search(keyword: str, count: int) -> list:
    """
    模拟微博搜索结果的函数。
    """
    mock_data = []
    
    # 构造一些带特定关键词的模拟内容，用于测试 classify_tweet
    content_templates = [
        # 交易类 (Trading)
        f"今日对 {keyword} 进行了一次做T操作，成功降低成本0.5%。这就是我的实盘记录。",
        f"最新调仓记录：清仓了A基金，加仓了B基金。分享我的买卖经验。",
        f"分析了宏观经济，我认为下周是最佳加仓时机，这只是个人账户的交易心得。",
        # 分析类 (Analysis)
        f"国家政策对 {keyword} 市场的影响将在Q4显现，这是一份专业的深度分析。",
        f"国际环境复杂，微观数据表明 {keyword} 仍将承压，请谨慎操作。",
        f"详细解读最新法规对个人投资者 {keyword} 账户的保护。",
        # 经验类 (Experience)
        f"我的 {keyword} 投资心得：长期主义才能带来真正的复利体会和经验。",
        f"分享一个我犯过的 {keyword} 投资错误，希望大家引以为戒，少走弯路。",
    ]
    
    # 确保每个分类都有数据
    for i in range(count):
        tweet_id = str(10000 + i)
        
        # 随机选择一个模板，并确保分类关键词被包含
        template = random.choice(content_templates)
        
        # 模拟生成数据
        mock_data.append({
            "content": template,
            "user": f"用户{i+1}",
            "time": (datetime.datetime.now() - datetime.timedelta(hours=random.randint(1, 48))).strftime("%Y-%m-%d %H:%M:%S"),
            "likes": random.randint(10, 500),
            "comments": random.randint(1, 100),
            "reposts": random.randint(0, 50),
            "search_keyword": keyword, # 记录是哪个关键词搜索到的
        })
        
    return mock_data


def search_weibo_keyword(keyword: str) -> list:
    """
    【!!! 关键函数：此处需要接入真实的 weibo-scraper 搜索逻辑 !!!】
    
    Args:
        keyword: 要搜索的关键词。
        
    Returns:
        包含微博内容的字典列表。
    """
    print(f"-> 正在尝试搜索关键词: {keyword}")
    
    # =========================================================================
    # WARNING: 占位符代码
    # 您必须使用 weibo-scraper 库的 API 替换下面的 mock_weibo_search(keyword, 30)
    #
    # 示例（假设存在一个 search_posts 函数）：
    # try:
    #     tweets = actual_search_api(keyword, pages=5, login_info=...)
    #     # 您可能还需要在这里编写逻辑，将 weibo-scraper 返回的 TweetMeta 对象
    #     # 转换为本脚本需要的字典格式 (content, user, time, likes, comments, reposts)
    #     
    #     # return [your_parsed_data_dictionary for tweet in tweets]
    # except Exception as e:
    #     print(f"ERROR: 微博搜索失败 ({keyword}): {e}")
    #     return []
    #
    # 重要的字段映射:
    # - content: mblog.text
    # - user: user.screen_name
    # - likes: mblog.attitudes_count
    # - comments: mblog.comments_count
    # - reposts: mblog.reposts_count
    # - time: mblog.created_at
    # =========================================================================

    # 使用模拟数据进行报告生成测试
    return mock_weibo_search(keyword, 30)


def generate_report(all_tweets: list, keywords_used: list):
    """
    根据抓取到的所有微博内容，进行分类整理并生成 Markdown 报告。
    """
    if not all_tweets:
        print("无抓取结果，跳过报告生成。")
        return

    # 1. 初始化分类字典
    classified_tweets = {
        "📊 个人实盘、买卖与交易记录": [],
        "📰 专业分析、政策与宏观影响": [],
        "🧠 经验、心得与体会分享": [],
        "🤔 其他讨论/未分类": [],
    }

    # 2. 自动分类
    for tweet in all_tweets:
        # 使用 classify_tweet 函数进行自动分类
        category = classify_tweet(tweet['content'])
        
        # 确保分类键存在，然后添加
        if category in classified_tweets:
            classified_tweets[category].append(tweet)
        else:
             # 如果分类结果不在预设的四个类别中，则放入“其他”
             classified_tweets["🤔 其他讨论/未分类"].append(tweet)


    # 3. 报告内容构建
    report_content = []
    
    # 报告头部
    report_content.append(f"# 📈 微博基金话题自动分类报告")
    report_content.append(f"\n**生成时间:** {datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    report_content.append(f"**搜索关键词:** {', '.join(keywords_used)}\n")
    report_content.append(f"**抓取总条数:** {len(all_tweets)} 条\n")
    report_content.append("---\n")


    # 4. 遍历分类并生成内容
    for category, tweets in classified_tweets.items():
        # 按点赞数降序排序，突显热门内容
        tweets.sort(key=lambda x: x['likes'], reverse=True)
        
        report_content.append(f"## {category} ({len(tweets)} 条)")
        
        if not tweets:
            report_content.append("暂无相关热门内容。\n")
            continue
            
        # 表格头部
        report_content.append("| 热门度 (点赞) | 用户 | 微博内容 (前100字) | 来源关键词 |")
        report_content.append("| :---: | :--- | :--- | :---: |")

        # 遍历该分类下的热门微博（仅展示前10条最热门的）
        for tweet in tweets[:10]:
            content_preview = tweet['content'][:100].replace('\n', ' ').replace('|', '-') + ('...' if len(tweet['content']) > 100 else '')
            
            # 使用 Markdown 格式化行
            row = (
                f"| {tweet['likes']} (💬{tweet['comments']}) "
                f"| @{tweet['user']} "
                f"| {content_preview} "
                f"| {tweet.get('search_keyword', 'N/A')} |"
            )
            report_content.append(row)
            
        report_content.append("\n---\n")

    # 5. 保存报告
    report_dir = 'reports'
    report_path = os.path.join(report_dir, 'report.md')
    
    # 确保 reports 目录存在
    os.makedirs(report_dir, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_content))
        
    print(f"✅ 报告已成功生成并保存到 {report_path}")


def main():
    """主执行函数，负责获取关键词、执行搜索和报告生成。"""
    
    # 从环境变量 KEYWORDS_ENV 获取关键词列表
    keywords_env = os.environ.get('KEYWORDS_ENV')
    
    if keywords_env:
        # 环境变量存在，按逗号分隔处理
        keywords_list = [k.strip() for k in keywords_env.split(',') if k.strip()]
        print(f"⚙️ 从环境变量 KEYWORDS_ENV 获取关键词: {keywords_list}")
    else:
        # 环境变量不存在，使用内部回退关键词
        keywords_list = ['基金']
        print(f"⚠️ 环境变量 KEYWORDS_ENV 未设置。使用内部回退关键词: {keywords_list}")

    if not keywords_list:
        print("❌ 关键词列表为空，程序退出。")
        return

    all_tweets = []
    
    # 遍历所有关键词进行搜索
    for keyword in keywords_list:
        # 在这里执行真正的微博搜索（目前是模拟数据）
        search_results = search_weibo_keyword(keyword)
        all_tweets.extend(search_results)
        time.sleep(1) # 模拟网络请求延迟，避免被封禁

    # 生成报告
    generate_report(all_tweets, keywords_list)

if __name__ == "__main__":
    main()
