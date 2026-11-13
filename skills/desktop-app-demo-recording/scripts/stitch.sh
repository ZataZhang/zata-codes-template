#!/usr/bin/env bash
# 把一个案例的一段或多段录屏拼成一个成片：开头 HEAD 秒、结尾 TAIL 秒保持原速，
# 中间等待 AI 干活的部分按 SPEED 倍快进。输出 H.264 + yuv420p，常见播放器都能播。
#
# 用法：stitch.sh <输出.mp4> <头部秒数> <尾部秒数> <段1.mp4> [段2.mp4 ...]
# 环境变量：SPEED（默认 8）、WIDTH（默认 1710，统一各段分辨率）
set -euo pipefail

if [ "$#" -lt 4 ]; then
    echo "用法: $0 <输出.mp4> <头部秒数> <尾部秒数> <段1.mp4> [段2.mp4 ...]" >&2
    exit 2
fi
for tool in ffmpeg ffprobe bc; do
    command -v "$tool" >/dev/null || { echo "缺少依赖: $tool" >&2; exit 2; }
done

output_path=$1
head_seconds=$2
tail_seconds=$3
shift 3
speed=${SPEED:-8}
width=${WIDTH:-1710}

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

# 先把各段统一成同样的分辨率、帧率和编码，再无损拼接。
segment_index=0
: > "$work_dir/list.txt"
for segment in "$@"; do
    ffmpeg -v error -y -i "$segment" -an -vf "scale=${width}:-2,fps=30" \
        -c:v libx264 -crf 20 -preset veryfast -pix_fmt yuv420p \
        "$work_dir/segment_${segment_index}.mp4"
    echo "file '$work_dir/segment_${segment_index}.mp4'" >> "$work_dir/list.txt"
    segment_index=$((segment_index + 1))
done
ffmpeg -v error -y -f concat -safe 0 -i "$work_dir/list.txt" -c copy "$work_dir/all.mp4"

total_seconds=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$work_dir/all.mp4")
middle_end=$(echo "$total_seconds - $tail_seconds" | bc -l)

# 总长不够放下头尾时没有可快进的中段，直接按原速输出。
if [ "$(echo "$middle_end <= $head_seconds" | bc -l)" -eq 1 ]; then
    ffmpeg -v error -y -i "$work_dir/all.mp4" -c:v libx264 -crf 23 -preset veryfast \
        -pix_fmt yuv420p "$output_path"
else
    ffmpeg -v error -y -i "$work_dir/all.mp4" -filter_complex "\
[0:v]trim=0:${head_seconds},setpts=PTS-STARTPTS[head];\
[0:v]trim=${head_seconds}:${middle_end},setpts=(PTS-STARTPTS)/${speed}[middle];\
[0:v]trim=${middle_end},setpts=PTS-STARTPTS[tail];\
[head][middle][tail]concat=n=3:v=1[out]" \
        -map "[out]" -c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p "$output_path"
fi

ffprobe -v error -show_entries format=duration -of csv=p=0 "$output_path"
