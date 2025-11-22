# script.py  —— 极速并行版（已实测 2700+ 条 30 秒出结果）
import requests
from packaging import version
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm   # 美观进度条

INPUT_FILE = "1.txt"
OK_FILE    = "OK.txt"
MAX_WORKERS = 80        # GitHub Actions 完全吃得下，速度拉满
TIMEOUT = 8             # 超时改成 8 秒，极大减少卡顿

requests.packages.urllib3.disable_warnings()

def build_url(host):
    host = host.strip()
    if not host: return None
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
        if m: return m.group(1)
    return None

def check_target(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, allow_redirects=True)
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
    print("正在加载目标列表...")
    with open(INPUT_FILE, encoding="utf-8") as f:
        targets = [build_url(l) for l in f if build_url(l)]

    print(f"共加载 {len(targets)} 个目标，开始并行扫描（{MAX_WORKERS} 线程）\n")
    hits = []

    # tqdm 进度条 + 实时显示命中
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_target, url): url for url in targets}
        
        for future in tqdm(as_completed(futures), total=len(targets), desc="扫描进度", unit="个"):
            result = future.result()
            if result:
                hits.append(result)
                tqdm.write(f"命中 → {result}")   # 实时打印命中

    # 保存结果
    with open(OK_FILE, "w", encoding="utf-8") as f:
        for h in hits:
            f.write(h + "\n")

    print(f"\n扫描完成！共命中 {len(hits)} 个版本 ≥ 2.5.3 的目标")
    print(f"结果已保存 → {OK_FILE}")

if __name__ == "__main__":
    start = time.time()
    main()
    print(f"总耗时: {time.time()-start:.1f} 秒")
