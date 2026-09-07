#!/bin/bash
# 测试公众号 API：取 token → 传封面 → 建草稿
# 用法: ./test_draft.sh   （优先读环境变量 GZH_APPID/GZH_APPSECRET，否则读同目录 .env 的 APPID/APPSECRET，输出不打印密钥）
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${GZH_APPID:-}" ] || [ -z "${GZH_APPSECRET:-}" ]; then
  set -a; source .env; set +a
  GZH_APPID="${GZH_APPID:-$APPID}"
  GZH_APPSECRET="${GZH_APPSECRET:-$APPSECRET}"
fi

echo "== 1. 获取 access_token =="
TOKEN_RESP=$(curl -s "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=${GZH_APPID}&secret=${GZH_APPSECRET}")
if echo "$TOKEN_RESP" | grep -q '"errcode"'; then
  echo "失败: $(echo "$TOKEN_RESP" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r.get("errcode"), r.get("errmsg"))')"
  exit 1
fi
TOKEN=$(echo "$TOKEN_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
echo "成功（token 已获取，不打印）"

echo "== 2. 上传封面图（永久素材） =="
COVER="../image/01_三种办公Agent怎么选/选型地图.png"
UPLOAD_RESP=$(curl -s -F "media=@${COVER};type=image/png" "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=${TOKEN}&type=image")
echo "$UPLOAD_RESP" | python3 -c 'import json,sys; r=json.load(sys.stdin); print("media_id:", r["media_id"]) if "media_id" in r else print("失败:", r)'
THUMB=$(echo "$UPLOAD_RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("media_id",""))')
[ -z "$THUMB" ] && exit 1

echo "== 3. 创建草稿 =="
DRAFT_BODY=$(python3 - "$THUMB" <<'EOF'
import json, sys
print(json.dumps({"articles":[{
  "title": "【API 测试】草稿箱链路验证",
  "author": "",
  "digest": "这是一条 API 自动化测试草稿，确认 token、素材上传、草稿创建三步可用，可直接删除。",
  "content": "<p>如果你看到这段话，说明 AppID/AppSecret、素材上传和草稿创建接口都通了。</p><p>这条草稿可以直接删除。</p>",
  "thumb_media_id": sys.argv[1],
  "need_open_comment": 0,
  "only_fans_can_comment": 0
}]}, ensure_ascii=False))
EOF
)
DRAFT_RESP=$(curl -s -X POST -H "Content-Type: application/json; charset=utf-8" --data-binary "$DRAFT_BODY" "https://api.weixin.qq.com/cgi-bin/draft/add?access_token=${TOKEN}")
echo "$DRAFT_RESP" | python3 -c 'import json,sys; r=json.load(sys.stdin); print("草稿创建成功，media_id:", r["media_id"]) if "media_id" in r else print("失败:", r)'
