#!/usr/bin/env bash
#
# 把本 Skill 从「当前所在的这份副本」同步回 Git 上游仓库。
#
# 为什么需要这个脚本，而不是直接 rsync：
#
# SKILL.md 曾经要求执行
#
#     rsync -a --delete <本机安装目录>/ <仓库>/skills/zata-writer/
#
# 这条命令让一份**没有版本控制的本机副本**单向覆盖 Git 仓库，而且带 --delete。
# 只要本机副本落后于仓库（例如有人直接在仓库里改了 references/），下一次同步就
# 会静默删掉仓库里的新内容——没有提示，没有确认，删完 rsync 照样返回 0。
#
# 2026-09-09 这件事真的发生了：references/gongzhong-publish.md 被抹掉 121 行，
# 正是两个提交前 0d2b85ba 刚补进去的「草稿 API 推送的额外限制」和「流程图兼容
# 写法」两节实测结论。删除混在一堆并行改动里，差一步就被提交进历史。
#
# 所以本脚本把「删除」从默认行为改成必须显式解释的例外：
#
#   1. 目标必须是干净的 Git 工作区。脏工作区意味着仓库侧有未提交改动，直接覆盖
#      就是上面那起事故的翻版，先去处理它。
#   2. 先 dry-run。一旦计划里出现删除就停下并打印清单——删除意味着「仓库里有、
#      本副本没有」，绝大多数情况是本副本过期，而不是有人想移除内容。
#   3. 确实要删时显式加 --allow-delete，删除清单仍会完整打印出来供复核。
#   4. 同步后打印 git status/diff --stat，由人复核后再决定提交。
#
# 反方向（仓库 -> 本机各 AI 助手的 skills 目录）已有仓库内的既有机制，不要在这里
# 另写一份：`just sync-local-skills`（scripts/shared/template/sync_template.sh
# --local-skills）会逐项列出差异、带 diff 交互选择。
#
# 用法：
#
#     assets/sync_upstream.sh <上游仓库的 skills/zata-writer 目录>
#     assets/sync_upstream.sh                      # 读环境变量 ZATA_WRITER_UPSTREAM
#     assets/sync_upstream.sh <目录> --allow-delete # 已复核过删除清单时
#
# 刻意不把上游路径写死在脚本或 SKILL.md 里：本机安装目录会随所用 AI 工具变化
# （.kimi-code -> .qoder-cn 就改过一次），写死的路径每换一次工具就要改一次文档，
# 而漏改的那次就会同步到错误的目录。

set -euo pipefail

# 源目录 = 本脚本所在的 Skill 根目录。脚本随 Skill 一起被复制，因此它永远指向
# 「正在运行的这份副本」，不需要任何配置。
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 不该进入仓库的本机产物：Python 缓存、macOS 元数据、以及可能装着公众号
# appid/secret 的 .env（仓库 .gitignore 已挡一层，这里再挡一层，避免明文密钥
# 落到仓库工作区里）。
RSYNC_EXCLUDES=(
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='.DS_Store'
    --exclude='.pytest_cache/'
    --exclude='.env'
)

log() { printf '%s\n' "$*"; }
fail() {
    printf '\n❌ %s\n' "$1" >&2
    shift
    for line in "$@"; do
        printf '   %s\n' "$line" >&2
    done
    exit 1
}

print_usage() {
    log "用法: $(basename "$0") <上游仓库的 skills/zata-writer 目录> [--allow-delete]"
    log ""
    log "  未传目录时读环境变量 ZATA_WRITER_UPSTREAM。"
    log "  --allow-delete  已复核删除清单、确认这些内容应当被移除时才加。"
}

allow_delete=false
target_input=""
for argument in "$@"; do
    case "$argument" in
        --allow-delete)
            allow_delete=true
            ;;
        -h | --help)
            print_usage
            exit 0
            ;;
        -*)
            fail "未知参数：$argument" "运行 $(basename "$0") --help 查看用法。"
            ;;
        *)
            target_input="$argument"
            ;;
    esac
done

if [ -z "$target_input" ]; then
    target_input="${ZATA_WRITER_UPSTREAM:-}"
fi

if [ -z "$target_input" ]; then
    fail "未指定上游目录。" \
        "传入模板仓库中的 skills/zata-writer 路径，或设置 ZATA_WRITER_UPSTREAM。" \
        "例如: $(basename "$0") ~/code/<模板仓库>/skills/zata-writer"
fi

# 展开 ~ 后再取绝对路径；目录不存在时明确报错，而不是让 rsync 悄悄创建一个新目录。
target_input="${target_input/#\~/$HOME}"
if [ ! -d "$target_input" ]; then
    fail "上游目录不存在：$target_input" \
        "这不像是模板仓库里的 skills/zata-writer；确认路径后重试。" \
        "（若确实是首次落地新仓库，请先手动 mkdir 并 git add，再跑本脚本。）"
fi
TARGET_DIR="$(cd "$target_input" && pwd)"

if [ "$SOURCE_DIR" = "$TARGET_DIR" ]; then
    log "✅ 源与上游是同一个目录（$TARGET_DIR），无需同步。"
    exit 0
fi

# 目标必须在 Git 工作区内：本脚本的全部安全性都建立在「仓库侧的改动可被 git
# 看见」之上。不在 Git 下就没有任何东西能兜住误删。
target_git_root="$(git -C "$TARGET_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$target_git_root" ]; then
    fail "上游目录不在 Git 工作区内：$TARGET_DIR" \
        "本脚本靠 git 兜住误删，因此拒绝往非 Git 目录做带 --delete 的同步。"
fi

# 脏工作区直接拒绝：仓库侧存在未提交改动时覆盖过去，改动就永久消失了（git 里
# 没有它的任何记录，reflog 也救不回来）。
dirty_paths="$(git -C "$target_git_root" status --porcelain -- "$TARGET_DIR")"
if [ -n "$dirty_paths" ]; then
    log "上游有未提交的改动："
    log "$dirty_paths"
    fail "上游 skills 目录不干净，拒绝覆盖。" \
        "这些改动只存在于工作区，被 rsync 覆盖后 git 也找不回来。" \
        "先在仓库里提交、stash 或还原它们，然后重跑本脚本。"
fi

log "源  (本副本): $SOURCE_DIR"
log "上游 (Git 仓库): $TARGET_DIR"
log ""

plan_file="$(mktemp)"
# shellcheck disable=SC2064
trap "rm -f '$plan_file'" EXIT

# -i 输出逐项变更清单，配合 --dry-run 得到「将会发生什么」的完整计划。
rsync -ai --delete --dry-run "${RSYNC_EXCLUDES[@]}" \
    "$SOURCE_DIR"/ "$TARGET_DIR"/ >"$plan_file"

deletion_lines="$(grep '^\*deleting' "$plan_file" || true)"

if [ -n "$deletion_lines" ] && [ "$allow_delete" != true ]; then
    log "以下内容存在于上游仓库、但本副本里没有，同步会删掉它们："
    log ""
    printf '%s\n' "$deletion_lines" | sed 's/^\*deleting  */  - /'
    log ""
    fail "检测到删除，已中止，上游未被改动。" \
        "「仓库有、本副本没有」通常说明本副本过期了，而不是这些内容该被移除。" \
        "先确认：这些文件是不是别人直接在仓库里加的、你本地还没拿到？" \
        "  · 若是（多数情况）：先把仓库版本取回本副本，再重跑本脚本。" \
        "  · 若确实要删：复核上面清单后加 --allow-delete 重跑。"
fi

if [ ! -s "$plan_file" ]; then
    log "✅ 两处已经一致，无需同步。"
    exit 0
fi

log "将要应用的变更："
log ""
sed 's/^/  /' "$plan_file"
log ""

if [ -n "$deletion_lines" ]; then
    log "⚠️  --allow-delete 已启用，上面标记 *deleting 的内容会被删除。"
    log ""
fi

rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SOURCE_DIR"/ "$TARGET_DIR"/

log "✅ 同步完成。上游仓库中的改动如下，请复核后再提交："
log ""
git -C "$target_git_root" status --short -- "$TARGET_DIR"
log ""
git -C "$target_git_root" diff --stat -- "$TARGET_DIR"
