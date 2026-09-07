#!/bin/bash
# 一键把文章推送为公众号草稿：./gzh_build/publish.sh 文章文件名
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?用法: ./gzh_build/publish.sh 文章文件名（可带或不带 .md）}"
NAME=$(basename "${NAME%.md}")
./gzh_build/build.sh "$NAME"
python3 ./gzh_build/push_draft.py "${NAME}_公众号版.html" "$NAME.md"
