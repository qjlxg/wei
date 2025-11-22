# script.py  —— 多线程并行版（默认 15 线程，可调）
import requests
from packaging import version
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "1.txt"
OK_FILE = "OK.txt"
THREADS = 15          # 这里改线程数，建议 10~30

requests.packages.urllib3.disable_warnings()

def get_url(line):
    host = line.strip()
    return f"https://{host}/login" if host else None

def extract_version(text):
    patterns = [
        r'BPB Panel.*?([0-9]+\.[0-9]+\.[0-9]+)',
        r'BPB Panel v([0-9]+\.[0-9]+\.[0-9]+)',
        r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m: return m.group(1)
    return None

def check_one(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=12, verify=False, allow_redirects=True)
        if r.status_code != 200:
            return None
        if "BPB Panel" not in r.text and "bpbpanel" not in r.text.lower():
            return None
        ver = extract_version(r.text)
        if ver and version.parse(ver) >= version.parse("2.5.3"):
            return f"{url}  # 版本: {ver}"
    except:
        pass
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"未找到 {INPUT_FILE}")
        return

    print(f"开始并行扫描（{THREADS} 线程），只保留 BPB Panel ≥ 2.5.3\n")
    targets = []
    with open(INPUT_FILE, encoding="utf-8") as f:
        for line in f:
            u = get_url(line)
            if u: targets.append(u)

    hits = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        future_to_url = {pool.submit(check_one, url): url for url in targets}
        for i, future in enumerate(as_completed(future_to_url), 1):
            result = future.result()
            if result:
                hits.append(result)
                print(f"[{i}/{len(targets)}] 命中 → {result}")
            else:
                print(f"[{i}/{len(targets)}] 未命中或超时", end="\r")

    # 保存结果
    with open(OK_FILE, "w", encoding="utf-8") as f:
        for h in hits:
            f.write(h + "\n")

    print(f"\n扫描完成！用时 {time.time()-start:.1f} 秒，共命中 {len(hits)} 个")
    print(f"结果已保存 → {OK_FILE}")

if __name__ == "__main__":
    main()
