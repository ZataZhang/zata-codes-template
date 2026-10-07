#!/bin/bash
# 一键生成剪贴板版并复制：先重建公众号版 HTML（避免用到过期产物），再由 to_clipboard.py 处理
# 用法: ./gzh_build/copy.sh 文章文件名 [--no-copy]（--no-copy 只写 _剪贴板版.html，不动剪贴板）
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?用法: ./gzh_build/copy.sh 文章文件名（可带或不带 .md）[--no-copy]}"
NAME=$(basename "${NAME%.md}")
shift
./gzh_build/build.sh "$NAME"
python3 ./gzh_build/to_clipboard.py "$NAME" "$@"
