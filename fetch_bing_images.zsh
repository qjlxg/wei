#!/bin/zsh
# 文件名: fetch_bing_images.zsh
# 版本: 1.6 - 兼容 GitHub Actions 和目录结构要求

# --- 配置 ---
# 设置图片分辨率
RESOLUTION="1920x1080"
# 目标图片目录
IMG_DIR="bing_images"
# 元数据目录 (可选)
METADATA_DIR="metadata"

# 检查依赖
command -v curl >/dev/null 2>&1 || { echo >&2 "Error: curl is required but not installed."; exit 1; }
command -v xmllint >/dev/null 2>&1 || { echo >&2 "Error: xmllint is required but not installed."; exit 1; }

# 设置索引和市场列表
local -i idx=${1:-0} # 默认抓取今天的图片
[[ idx -gt 14 ]] && echo 'index too large' >&2 && exit $idx
local -i n=1
[[ idx -gt 7 ]] && n=$((idx-6))
local mkt

# 确保目标目录存在
mkdir -p $IMG_DIR
mkdir -p $METADATA_DIR

# 市场列表 (使用您提供的完整列表)
for mkt in {EN-US,JA-JP,ZH-CN,EN-IN,DE-DE,ES-ES,FR-FR,IT-IT,EN-GB,PT-BR,EN-CA}
do
    echo "--- Fetching market: $mkt (idx=$idx, n=$n) ---"
    local image=""
    
    # 循环直到成功获取数据 (保持您原脚本的健壮性)
    while [[ -z $image ]]; do
        image=$(curl -sS -d idx=$idx -d n=$n -d mkt=$mkt https://www.bing.com/HPImageArchive.aspx)
        # 避免无限循环，如果失败，等待1秒
        [[ -z $image ]] && sleep 1
    done

    # 解析数据 (注意：假设只抓取最新的 n=1 的数据进行处理，以简化路径逻辑)
    local enddate=$(echo $image | xmllint --xpath '//enddate/text()' - | head -n1)
    local urlBase=$(echo $image | xmllint --xpath '//urlBase/text()' - | head -n1)
    local copyright=$(echo $image | xmllint --xpath '//copyright/text()' - | head -n1)
    
    if [[ -n $urlBase && -n $enddate ]]; then
        # 1. 构造文件名（原始文件名）
        local filename=${urlBase#*/search*} # 移除 /search 之后的部分
        filename=${filename%%_*} # 截取到第一个下划线前
        
        # 2. 构造时间戳和最终路径 (上海时区)
        # Bing enddate 格式为 YYYYMMDD。我们将其转换为上海时区的时间戳。
        # 注意：Shell 的 date 命令很难精确处理时区转换，所以我们使用 enddate 作为基础日期。
        
        # 提取年、月、日
        local year=${enddate:0:4}
        local month=${enddate:4:2}
        local day=${enddate:6:2}
        
        # 构造保存路径: bing_images/年/月
        local target_dir="$IMG_DIR/$year/$month"
        mkdir -p "$target_dir"
        
        # 构造带时间戳的文件名（精确到日，时间设为 000000）
        # 文件名格式: YYYYMMDD_HHMMSS_原始文件名.jpg
        local timestamp="${year}${month}${day}_000000"
        local final_filename="${timestamp}_${filename}_${mkt}.jpg"
        local filepath="$target_dir/$final_filename"
        
        # 3. 下载图片 (如果文件不存在)
        if [[ ! -e "$filepath" ]]; then
            echo "Downloading image: $filepath"
            curl -so "$filepath" "https://www.bing.com${urlBase}_${RESOLUTION}.jpg"
            echo "Downloaded: $filepath"
        else
            echo "Image already exists: $filepath"
        fi
        
        # 4. 记录元数据 (可选)
        echo "$enddate,$filename,$mkt,\"$copyright\"" >> "$METADATA_DIR/bing_metadata_$mkt.csv"
    else
        echo "Error: Failed to parse enddate or urlBase for market $mkt."
    fi
done

echo "Script finished. Check the $IMG_DIR directory."
