#!/bin/bash
# 生成公众号版 HTML：./gzh_build/build.sh 01_三种办公Agent怎么选
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?用法: ./gzh_build/build.sh 文章文件名（可带或不带 .md）}"
NAME=$(basename "${NAME%.md}")
TITLE=$(head -1 "$NAME.md" | sed 's/^# *//')
TMP=$(mktemp /tmp/gzh.XXXXXX.md)
tail -n +2 "$NAME.md" > "$TMP"
if [ -f "gzh_build/$NAME.highlights.sed" ]; then
  sed -i '' -f "gzh_build/$NAME.highlights.sed" "$TMP"
fi
pandoc "$TMP" -f markdown+mark -t html5 -s --metadata title="$TITLE" -H gzh_build/style.html -o "${NAME}_公众号版.html"
python3 gzh_build/decorate.py "${NAME}_公众号版.html"
rm -f "$TMP"
echo "已生成 ${NAME}_公众号版.html"
