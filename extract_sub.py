import re
from urllib.parse import urlparse

def extract_links(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 按照区块分割 
    # 匹配以 [http 开始的行，直到下一个区块或结尾 
    blocks = re.split(r'\n(?=\[http)', content)
    results = []

    for block in blocks:
        # 排除包含“失败”字样的区块 
        if "失败" in block:
            continue
        
        # 1. 提取 [] 中的网址 
        header_url_match = re.search(r'^\[(https?://[^\]]+)\]', block.strip())
        
        # 2. 提取 sub_url 并截取域名部分 [cite: 1, 7]
        sub_url_match = re.search(r'sub_url\s+(https?://[^\/\s]+/)', block)
        # 如果 sub_url 后面没有斜杠，则匹配到末尾
        if not sub_url_match:
            sub_url_match = re.search(r'sub_url\s+(https?://[^\s]+)', block)

        if header_url_match and sub_url_match:
            header_url = header_url_match.group(1).strip()
            # 格式化 sub_url 域名部分，确保以 / 结尾 [cite: 7]
            parsed = urlparse(sub_url_match.group(1).strip())
            base_sub_url = f"{parsed.scheme}://{parsed.netloc}/"
            
            results.append(header_url)
            results.append(base_sub_url)

    # 去重并保持顺序
    final_list = list(dict.fromkeys(results))

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_list))

if __name__ == "__main__":
    extract_links('trial.cache', 'extract_sub.txt')
