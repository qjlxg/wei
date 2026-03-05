import re

def extract_urls(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 按照 [http... 分割块
    blocks = re.split(r'\n(?=\[http)', content)
    valid_subs = []

    for block in blocks:
        # 过滤掉包含“失败”的块
        if "失败" in block:
            continue
        
        # 提取名称和订阅链接
        name_match = re.search(r'name\s+(.*)', block)
        url_match = re.search(r'sub_url\s+(https?://\S+)', block)
        
        if name_match and url_match:
            name = name_match.group(1).strip()
            url = url_match.group(1).strip()
            valid_subs.append(f"{name}: {url}")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(valid_subs))

if __name__ == "__main__":
    
    extract_urls('trial.cache', 'extract_sub.txt')
