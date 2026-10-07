#!/bin/bash
# 生成公众号版 HTML：./gzh_build/build.sh 01_三种办公Agent怎么选
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?用法: ./gzh_build/build.sh 文章文件名（可带或不带 .md）}"
NAME=$(basename "${NAME%.md}")
TITLE=$(head -1 "$NAME.md" | sed 's/^# *//')
# X 必须放在模板末尾：macOS 的 mktemp 不替换后缀前的 X，会退化成固定文件名，
# 中途失败残留后每次构建都报 File exists。trap 保证失败退出时也清理。
TMP=$(mktemp /tmp/gzh.XXXXXX)
trap 'rm -f "$TMP"' EXIT
tail -n +2 "$NAME.md" > "$TMP"
if [ -f "gzh_build/$NAME.highlights.sed" ]; then
  sed -i '' -f "gzh_build/$NAME.highlights.sed" "$TMP"
fi
pandoc "$TMP" -f markdown+mark -t html5 -s --metadata title="$TITLE" -H gzh_build/style.html -o "${NAME}_公众号版.html"
python3 gzh_build/decorate.py "${NAME}_公众号版.html"
echo "已生成 ${NAME}_公众号版.html"
