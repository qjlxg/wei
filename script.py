# script.py  —— 极简版：只找 BPB Panel 版本 ≥ 2.5.3
import requests
import re
from packaging import version
import time
import os

# 输入文件（支持纯IP或域名，一行一个）
INPUT_FILE = "1.txt"
# 最终结果文件
OK_FILE = "OK.txt"

# 关闭 SSL 警告（很多面板自签证书）
requests.packages.urllib3.disable_warnings()

def get_target_url(line):
    host = line.strip()
    if not host:
        return None
    return f"https://{host}/login"

def extract_version(text):
    patterns = [
        r'BPB Panel.*?([0-9]+\.[0-9]+\.[0-9]+)',
        r'BPB Panel v([0-9]+\.[0-9]+\.[0-9]+)',
        r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
        r'Version[:\s]*([0-9]+\.[0-9]+\.[0-9]+)',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1)
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"错误：未找到 {INPUT_FILE} 文件！")
        return

    print("开始扫描，只保留 BPB Panel 版本 ≥ 2.5.3 的目标\n")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    min_ver = version.parse("2.5.3")
    hits = []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        targets = [get_target_url(line) for line in f if get_target_url(line)]

    total = len(targets)
    for i, url in enumerate(targets, 1):
        print(f"[{i}/{total}] {url}", end="  →  ")
        try:
            r = requests.get(url, headers=headers, timeout=12, verify=False, allow_redirects=True)
            if r.status_code != 200:
                print("状态码错误")
                continue
            if "BPB Panel" not in r.text and "bpbpanel" not in r.text.lower():
                print("非BPB面板")
                continue

            ver = extract_version(r.text)
            if ver and version.parse(ver) >= min_ver:
                result = f"{url}  # 版本: {ver}"
                print(f"命中！{ver}")
                hits.append(result)
            else:
                print(f"版本过低 {ver or '无'}")
        except Exception as e:
            print(f"连接失败")
        time.sleep(0.5)  # 友好扫描

    # 保存结果
    with open(OK_FILE, "w", encoding="utf-8") as f:
        for line in hits:
            f.write(line + "\n")

    print(f"\n扫描完成！共找到 {len(hits)} 个版本 ≥ 2.5.3 的目标")
    print(f"结果已保存到：{OK_FILE}")

if __name__ == "__main__":
    main()
