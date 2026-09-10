#!/bin/bash
# 生成网页版单文件 HTML：build_web.sh 文章.md路径 [kicker] [副标题]
# 在 Skill 资产目录原地运行，不向文章目录拷贝任何构建文件；文章目录只新增最终 HTML。
set -euo pipefail
GZH_DIR="$(cd "$(dirname "$0")" && pwd)"
ARTICLE="${1:?用法: build_web.sh 文章.md路径 [kicker] [副标题]}"
if [ ! -f "$ARTICLE" ] && [ -f "${ARTICLE}.md" ]; then ARTICLE="${ARTICLE}.md"; fi
[ -f "$ARTICLE" ] || { echo "找不到文章: $ARTICLE" >&2; exit 1; }
ARTICLE="$(cd "$(dirname "$ARTICLE")" && pwd)/$(basename "$ARTICLE")"
DIR="$(dirname "$ARTICLE")"
NAME="$(basename "${ARTICLE%.md}")"
cd "$DIR"
KICKER="${2:-Zata 山外志 · 手记}"
SUBTITLE="${3:-}"
TITLE=$(head -1 "$ARTICLE" | sed 's/^# *//')
TMP=$(mktemp /tmp/gzhweb.XXXXXX.md)
tail -n +2 "$ARTICLE" > "$TMP"
if [ -f "gzh_build/$NAME.highlights.sed" ]; then
  sed -i '' -f "gzh_build/$NAME.highlights.sed" "$TMP"
fi
pandoc "$TMP" -f markdown+mark -t html5 -s --toc --toc-depth=2 \
  --metadata title="$TITLE" -H "$GZH_DIR/style_web.html" -o "${NAME}_网页版.html"
python3 "$GZH_DIR/postprocess_web.py" "${NAME}_网页版.html" "$KICKER" "$SUBTITLE"
rm -f "$TMP"
echo "已生成 $DIR/${NAME}_网页版.html"
