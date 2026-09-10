#!/bin/bash
# 生成网页版单文件 HTML：./gzh_build/build_web.sh 文章名 [kicker] [副标题]
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?用法: ./gzh_build/build_web.sh 文章文件名（可带或不带 .md）}"
NAME=$(basename "${NAME%.md}")
KICKER="${2:-Zata 山外志 · 手记}"
SUBTITLE="${3:-}"
TITLE=$(head -1 "$NAME.md" | sed 's/^# *//')
TMP=$(mktemp /tmp/gzhweb.XXXXXX.md)
tail -n +2 "$NAME.md" > "$TMP"
if [ -f "gzh_build/$NAME.highlights.sed" ]; then
  sed -i '' -f "gzh_build/$NAME.highlights.sed" "$TMP"
fi
pandoc "$TMP" -f markdown+mark -t html5 -s --toc --toc-depth=2 \
  --metadata title="$TITLE" -H gzh_build/style_web.html -o "${NAME}_网页版.html"
python3 gzh_build/postprocess_web.py "${NAME}_网页版.html" "$KICKER" "$SUBTITLE"
rm -f "$TMP"
echo "已生成 ${NAME}_网页版.html"
