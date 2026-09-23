#!/usr/bin/env bash
# 构建 OCI 镜像、推送到 ACR，并通过官方 e2b SDK 发布 FC Sandbox 模板。
# 用法：deploy/sandbox/build_e2b_template.sh [模板名称]
#
# 必填环境变量：E2B_API_KEY / E2B_API_URL / E2B_DOMAIN、
# E2B_TEMPLATE_IMAGE、E2B_REGISTRY_USERNAME / E2B_REGISTRY_PASSWORD。

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dockerfile_path="${repository_root}/deploy/sandbox/Dockerfile.e2b-template"

if [[ "${E2B_SKIP_DOTENV:-0}" != "1" ]]; then
    for env_file in "${repository_root}/.env" "${repository_root}/.env.local"; do
        if [[ -f "${env_file}" ]]; then
            set -a
            # shellcheck disable=SC1090
            source "${env_file}"
            set +a
        fi
    done
fi

require_env() {
    local variable_name="$1"
    if [[ -z "${!variable_name:-}" ]]; then
        echo "缺少 ${variable_name}；请在 .env.local 中配置。" >&2
        exit 1
    fi
}

read_e2b_config_value() {
    local config_key="$1"
    uv run --no-sync --quiet python - "${repository_root}/config.toml" "${config_key}" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as config_file:
    config_data = tomllib.load(config_file)
print(config_data.get("sandbox_agent", {}).get("e2b", {}).get(sys.argv[2], ""))
PY
}

command -v docker >/dev/null 2>&1 || { echo "缺少 docker 命令。" >&2; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "缺少 uv 命令。" >&2; exit 1; }
[[ -f "${dockerfile_path}" ]] || { echo "找不到 ${dockerfile_path}" >&2; exit 1; }

template_name_prefix="${1:-}"
if [[ -z "${template_name_prefix}" ]]; then
    template_name_prefix="$(read_e2b_config_value template_id)"
fi
if [[ -z "${E2B_API_URL:-}" ]]; then
    E2B_API_URL="$(read_e2b_config_value api_url)"
fi

require_env E2B_API_KEY
require_env E2B_API_URL
require_env E2B_DOMAIN
require_env E2B_TEMPLATE_IMAGE
require_env E2B_REGISTRY_USERNAME
require_env E2B_REGISTRY_PASSWORD
[[ -n "${template_name_prefix}" ]] || { echo "缺少模板名称前缀。" >&2; exit 1; }

image_registry="${E2B_TEMPLATE_IMAGE%%/*}"
image_last_component="${E2B_TEMPLATE_IMAGE##*/}"
if [[ "${image_registry}" == "${E2B_TEMPLATE_IMAGE}" || "${image_last_component}" != *:* ]]; then
    echo "E2B_TEMPLATE_IMAGE 必须是带显式 tag 的完整仓库地址。" >&2
    exit 1
fi

echo "登录镜像仓库：${image_registry}"
printf '%s' "${E2B_REGISTRY_PASSWORD}" | docker login "${image_registry}" \
    --username "${E2B_REGISTRY_USERNAME}" --password-stdin >/dev/null

echo "构建并推送 linux/amd64 OCI 镜像：${E2B_TEMPLATE_IMAGE}"
docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --sbom=false \
    --file "${dockerfile_path}" \
    --tag "${E2B_TEMPLATE_IMAGE}" \
    --push \
    "${repository_root}"

export E2B_API_URL E2B_DOMAIN E2B_TEMPLATE_IMAGE
export E2B_TEMPLATE_NAME="${template_name_prefix}-$(date +%Y%m%d%H%M%S)"

echo "从 OCI 镜像发布模板：${E2B_TEMPLATE_NAME}"
uv run --no-project --with e2b==2.32.0 python - <<'PY'
import os
import sys

from e2b import Sandbox, Template, default_build_logger
from e2b.exceptions import BuildException


def positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    value = int(raw) if raw else default
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


options = {
    "api_key": os.environ["E2B_API_KEY"],
    "api_url": os.environ["E2B_API_URL"],
    "domain": os.environ["E2B_DOMAIN"],
}
template_name = os.environ["E2B_TEMPLATE_NAME"]
definition = Template().from_image(
    os.environ["E2B_TEMPLATE_IMAGE"],
    username=os.environ["E2B_REGISTRY_USERNAME"],
    password=os.environ["E2B_REGISTRY_PASSWORD"],
)
for attempt in range(2):
    build_name = template_name if attempt == 0 else f"{template_name}-retry"
    try:
        build = Template.build(
            definition,
            name=build_name,
            cpu_count=positive_int("E2B_TEMPLATE_CPU_COUNT", 2),
            memory_mb=positive_int("E2B_TEMPLATE_MEMORY_MB", 2048),
            on_build_logs=default_build_logger(),
            **options,
        )
        break
    except BuildException as exc:
        if attempt or "user jurisdiction error" not in str(exc):
            raise
        print("ACR 授权令牌暂时失败，使用新模板名称重试一次。", file=sys.stderr)
else:  # pragma: no cover - 循环只会 break 或 raise
    raise RuntimeError("模板构建未返回结果")
print(f"模板已就绪：name={build_name} templateID={build.template_id}")

print("创建临时沙箱并验证目录、Python 数据依赖与 Node.js……")
sandbox = Sandbox.create(
    template=build.template_id,
    timeout=300,
    metadata={"purpose": "template-smoke-test"},
    allow_internet_access=False,
    **options,
)
try:
    result = sandbox.commands.run(
        "set -eu; test \"$(id -u)\" != 0; "
        "test -w /workspace/inputs; test -w /workspace/outputs; "
        "test -w /large_tool_results; test -w /conversation_history; "
        "python -c \"import openpyxl,pandas,numpy,scipy; "
        "print(openpyxl.__version__,pandas.__version__,numpy.__version__,scipy.__version__)\"; "
        "node --version"
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.exit_code != 0:
        raise RuntimeError(f"模板 smoke test 失败，退出码 {result.exit_code}")
finally:
    sandbox.kill()
print("模板 smoke test 通过，临时沙箱已释放。")
print(f"请把 config.toml 的 template_id 更新为：{build.template_id}")
PY
