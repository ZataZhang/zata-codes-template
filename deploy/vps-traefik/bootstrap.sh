#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# bootstrap.sh - interactive one-shot VPS app preparation.
#
# Run on your local machine after the server has Docker and host-level Traefik.
# This script prepares the application directory, deploy user, SSH key, compose
# files, and initial env files for a template-derived project.
#
# Usage examples:
#   ./deploy/vps-traefik/bootstrap.sh
#   ./deploy/vps-traefik/bootstrap.sh --server 1.2.3.4 --domain app.example.com
#   ./deploy/vps-traefik/bootstrap.sh --app-slug my-app --server 1.2.3.4 --domain app.example.com -y
# -----------------------------------------------------------------------------
set -euo pipefail

APP_SLUG="zata-codes-template"
ADMIN_USER="root"
DEPLOY_USER="deploy"
APP_DIR=""
TRAEFIK_NETWORK="traefik"
KEY_DIR="${HOME}/.ssh"
KEY_NAME=""
SERVER=""
DOMAIN=""
ASSUME_YES=0

if [[ -t 1 ]]; then
  C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[1;31m'; C_CYAN=$'\033[1;36m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_DIM=""; C_RESET=""
fi

log()     { printf '%s[bootstrap]%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()      { printf '  %sOK%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()    { printf '%s[bootstrap]%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
fail()    { printf '%s[bootstrap]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; cleanup_ssh; exit 1; }
section() { printf '\n%s--- %s ---%s\n' "$C_CYAN" "$*" "$C_RESET"; }

prompt() {
  local varname="$1" question="$2" default="${3:-}" value
  if [[ -n "$default" ]]; then
    printf '  %s [%s%s%s]: ' "$question" "$C_DIM" "$default" "$C_RESET"
  else
    printf '  %s: ' "$question"
  fi
  IFS= read -r value </dev/tty
  [[ -z "$value" ]] && value="$default"
  [[ -z "$value" ]] && fail "Value required for $varname"
  printf -v "$varname" '%s' "$value"
}

confirm() {
  local message="$1" default="${2:-N}" answer hint
  (( ASSUME_YES )) && return 0
  [[ "$default" == "Y" ]] && hint="[Y/n]" || hint="[y/N]"
  printf '  %s %s: ' "$message" "$hint"
  IFS= read -r answer </dev/tty
  [[ -z "$answer" ]] && answer="$default"
  [[ "$answer" =~ ^[Yy]$ ]]
}

shell_quote() {
  printf '%q' "$1"
}

upsert_env_file_value() {
  local target_file="$1" env_key="$2" env_value="$3"
  if grep -q "^${env_key}=" "$target_file"; then
    sed -i.bak "s#^${env_key}=.*#${env_key}=${env_value}#" "$target_file"
    rm -f "${target_file}.bak"
  else
    printf '%s=%s\n' "$env_key" "$env_value" >> "$target_file"
  fi
}

SSH_CTRL=""
SSH_BASE_OPTS=(-o "StrictHostKeyChecking=accept-new")
SSH_ADMIN_OPTS=()

init_ssh_master() {
  SSH_CTRL="$(mktemp -u "/tmp/ssh-bootstrap-XXXXXX.sock")"
  SSH_ADMIN_OPTS=(
    "${SSH_BASE_OPTS[@]}"
    -o "ControlMaster=auto"
    -o "ControlPath=${SSH_CTRL}"
    -o "ControlPersist=10m"
  )
}

cleanup_ssh() {
  if [[ -n "${SSH_CTRL:-}" ]] && [[ -S "$SSH_CTRL" ]]; then
    ssh -O exit "${SSH_ADMIN_OPTS[@]}" "${ADMIN_USER}@${SERVER}" 2>/dev/null || true
  fi
}
trap cleanup_ssh EXIT

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Common flags:
  --server HOST           Server hostname or IP.
  --domain DOMAIN         Public domain Traefik should route to.
  --app-slug SLUG         Project slug. Default: ${APP_SLUG}.
  --admin-user USER       Admin SSH user. Default: root.
  --root-user USER        Alias for --admin-user.
  --deploy-user USER      Unprivileged CD user. Default: ${DEPLOY_USER}.
  --app-dir PATH          App directory. Default: /opt/apps/<app-slug>.
  --traefik-network NAME  External Traefik network. Default: ${TRAEFIK_NETWORK}.
  --key-dir DIR           Local SSH key directory. Default: ${KEY_DIR}.
  --key-name NAME         Local SSH key filename. Default: cd-<app-slug>.
  -y, --yes               Skip confirmation prompts.
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server)          SERVER="$2"; shift 2 ;;
    --domain)          DOMAIN="$2"; shift 2 ;;
    --app-slug)        APP_SLUG="$2"; shift 2 ;;
    --admin-user|--root-user) ADMIN_USER="$2"; shift 2 ;;
    --deploy-user)     DEPLOY_USER="$2"; shift 2 ;;
    --app-dir)         APP_DIR="$2"; shift 2 ;;
    --traefik-network) TRAEFIK_NETWORK="$2"; shift 2 ;;
    --key-dir)         KEY_DIR="$2"; shift 2 ;;
    --key-name)        KEY_NAME="$2"; shift 2 ;;
    -y|--yes)          ASSUME_YES=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)                 warn "Unknown option: $1"; usage; exit 1 ;;
  esac
done

command -v ssh >/dev/null || fail "ssh not found in PATH"
command -v scp >/dev/null || fail "scp not found in PATH"
command -v ssh-keygen >/dev/null || fail "ssh-keygen not found in PATH"
command -v openssl >/dev/null || fail "openssl not found in PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for template in docker-compose.yml .env.example app.env.example; do
  [[ -f "${SCRIPT_DIR}/${template}" ]] || fail "Template '${template}' missing from ${SCRIPT_DIR}."
done

cat <<EOF

  ${C_CYAN}VPS Traefik deploy bootstrap${C_RESET}

  Prepares a server directory for a template-derived app. Re-runs are safe:
  existing users, authorized keys, .env, and app.env are kept.

EOF

section "Step 1/5  Collect inputs"

[[ -z "$SERVER" ]] && prompt SERVER "Server hostname or IP"
prompt ADMIN_USER "Admin SSH user (root, ubuntu, ec2-user, ...)" "$ADMIN_USER"
[[ -z "$DOMAIN" ]] && prompt DOMAIN "Public domain Traefik should route to"

if (( ! ASSUME_YES )); then
  echo
  log "Advanced options (press Enter to accept defaults):"
  prompt APP_SLUG        "Project slug"              "$APP_SLUG"
fi

[[ -n "$APP_DIR" ]] || APP_DIR="/opt/apps/${APP_SLUG}"
[[ -n "$KEY_NAME" ]] || KEY_NAME="cd-${APP_SLUG}"

if (( ! ASSUME_YES )); then
  prompt DEPLOY_USER     "Deploy user"               "$DEPLOY_USER"
  prompt APP_DIR         "App directory on server"   "$APP_DIR"
  prompt TRAEFIK_NETWORK "Traefik Docker network"    "$TRAEFIK_NETWORK"
  prompt KEY_DIR         "Local SSH key directory"   "$KEY_DIR"
  prompt KEY_NAME        "Local SSH key filename"    "$KEY_NAME"
fi

PRIVATE_KEY="${KEY_DIR}/${KEY_NAME}"
PUBLIC_KEY="${PRIVATE_KEY}.pub"

echo
log "Summary:"
echo "    App slug       ${APP_SLUG}"
echo "    Admin login    ${ADMIN_USER}@${SERVER}"
echo "    Deploy user    ${DEPLOY_USER}"
echo "    Domain         ${DOMAIN}"
echo "    Traefik net    ${TRAEFIK_NETWORK}"
echo "    App dir        ${APP_DIR}"
echo "    Local key      ${PRIVATE_KEY}"
echo
confirm "Proceed?" Y || fail "Aborted."

section "Step 2/5  Local SSH key for CD"

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

if [[ -f "$PRIVATE_KEY" ]]; then
  ok "Reusing existing key: $PRIVATE_KEY"
else
  log "Generating ed25519 key at $PRIVATE_KEY"
  ssh-keygen -t ed25519 -C "$KEY_NAME" -f "$PRIVATE_KEY" -N "" -q
  ok "Key generated"
fi
[[ -f "$PUBLIC_KEY" ]] || fail "Public key missing: $PUBLIC_KEY"
PUBKEY_CONTENT="$(cat "$PUBLIC_KEY")"

section "Step 3/5  Server bootstrap"

init_ssh_master

PROBE_RAW=$(ssh "${SSH_ADMIN_OPTS[@]}" "${ADMIN_USER}@${SERVER}" \
  "TRAEFIK_NETWORK=$(shell_quote "$TRAEFIK_NETWORK") bash -s" <<'REMOTE' 2>/dev/null || echo "")
set -euo pipefail
for candidate in /opt/traefik /root/traefik /home/*/traefik /etc/traefik; do
  for path in $candidate; do
    if [ -f "$path/traefik.yml" ]; then
      echo "DIR=$path"
      grep -E 'email:' "$path/traefik.yml" 2>/dev/null || true
      [ -f "$path/letsencrypt/acme.json" ] && echo ACME_JSON_PRESENT
      break 2
    fi
  done
done
docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 && echo TRAEFIK_NETWORK_PRESENT
REMOTE

TRAEFIK_DIR_ON_SERVER=$(echo "$PROBE_RAW" | sed -n 's/^DIR=//p' | head -1)
TRAEFIK_ACME_EMAIL_ON_SERVER=$(echo "$PROBE_RAW" \
  | sed -n 's/.*email:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
TRAEFIK_HAS_ACME_JSON=$(echo "$PROBE_RAW" | grep -q ACME_JSON_PRESENT && echo yes || echo no)
TRAEFIK_NETWORK_PRESENT=$(echo "$PROBE_RAW" | grep -q TRAEFIK_NETWORK_PRESENT && echo yes || echo no)

if [[ "$TRAEFIK_NETWORK_PRESENT" != "yes" ]]; then
  warn "Docker network '${TRAEFIK_NETWORK}' was not found on the server."
  warn "Run install-docker-traefik.sh first, or pass --traefik-network with the existing network name."
  confirm "Continue anyway?" N || fail "Aborted."
fi

PLACEHOLDER_EMAIL_PATTERN='^(admin@example\.com|you@example\.com|example\.com|.*@example\.com)$'
if [[ -n "$TRAEFIK_DIR_ON_SERVER" ]] && [[ -z "$TRAEFIK_ACME_EMAIL_ON_SERVER" || \
     "$TRAEFIK_ACME_EMAIL_ON_SERVER" =~ $PLACEHOLDER_EMAIL_PATTERN ]]; then
  warn "Traefik ACME email is missing or still a placeholder at ${TRAEFIK_DIR_ON_SERVER}/traefik.yml."
  warn "Use fix-acme-email.sh or rerun install-docker-traefik.sh with ACME_EMAIL=you@your-domain.com."
  confirm "Proceed anyway?" N || fail "Aborted. Fix Traefik ACME email first."
elif [[ -n "$TRAEFIK_DIR_ON_SERVER" && "$TRAEFIK_HAS_ACME_JSON" != "yes" ]]; then
  warn "No acme.json found under ${TRAEFIK_DIR_ON_SERVER}/letsencrypt."
  warn "The first HTTPS request may still show Traefik's default certificate until ACME succeeds."
  confirm "Continue anyway?" N || fail "Aborted."
fi

log "About to SSH ${ADMIN_USER}@${SERVER} and prepare ${APP_DIR}."
confirm "Continue?" Y || fail "Aborted."

ssh "${SSH_ADMIN_OPTS[@]}" "${ADMIN_USER}@${SERVER}" \
  "DEPLOY_USER=$(shell_quote "$DEPLOY_USER") APP_DIR=$(shell_quote "$APP_DIR") PUBKEY=$(shell_quote "$PUBKEY_CONTENT") bash -s" <<'REMOTE'
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  if ! command -v sudo >/dev/null 2>&1; then
    echo "ERROR: Not root and sudo is not installed." >&2
    exit 1
  fi
  if ! sudo -n true 2>/dev/null; then
    echo "ERROR: User '$(whoami)' needs passwordless sudo for this bootstrap." >&2
    exit 1
  fi
  SUDO="sudo"
fi

if id "$DEPLOY_USER" >/dev/null 2>&1; then
  echo "user ${DEPLOY_USER} already exists"
else
  $SUDO adduser --disabled-password --gecos "" "$DEPLOY_USER"
  echo "user ${DEPLOY_USER} created"
fi

if id -nG "$DEPLOY_USER" | tr ' ' '\n' | grep -qx docker; then
  echo "${DEPLOY_USER} already in docker group"
else
  $SUDO usermod -aG docker "$DEPLOY_USER"
  echo "added ${DEPLOY_USER} to docker group"
fi

$SUDO install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
AUTHKEYS="/home/${DEPLOY_USER}/.ssh/authorized_keys"
$SUDO touch "$AUTHKEYS"
$SUDO chmod 600 "$AUTHKEYS"
$SUDO chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTHKEYS"

if $SUDO grep -qxF "$PUBKEY" "$AUTHKEYS"; then
  echo "public key already authorized"
else
  printf '%s\n' "$PUBKEY" | $SUDO tee -a "$AUTHKEYS" >/dev/null
  echo "public key appended"
fi

$SUDO mkdir -p "$APP_DIR"
$SUDO chown "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
echo "${APP_DIR} ready"
REMOTE
ok "Server bootstrap complete"

section "Step 4/5  Verify deploy user"

ssh -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" -o BatchMode=yes \
  "${DEPLOY_USER}@${SERVER}" 'whoami >/dev/null && docker ps -q >/dev/null' \
  || fail "Verification failed. Check Docker installation and deploy user's docker group membership."
ok "Verification passed"

section "Step 5/5  Upload templates"

log "Uploading docker-compose.yml to ${DEPLOY_USER}@${SERVER}:${APP_DIR}/docker-compose.yml"
confirm "Continue?" Y || fail "Aborted."

scp -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" -q \
  "${SCRIPT_DIR}/docker-compose.yml" \
  "${DEPLOY_USER}@${SERVER}:${APP_DIR}/docker-compose.yml"
ok "docker-compose.yml uploaded"

LOCAL_ENV_FILE="$(mktemp)"
LOCAL_APP_ENV_FILE="$(mktemp)"
cleanup_local_seed_files() {
  rm -f "$LOCAL_ENV_FILE" "$LOCAL_APP_ENV_FILE"
}
trap 'cleanup_local_seed_files; cleanup_ssh' EXIT

if ssh -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" "${DEPLOY_USER}@${SERVER}" "[ -f '${APP_DIR}/.env' ]"; then
  ok "${APP_DIR}/.env already exists, leaving it alone"
else
  cp "${SCRIPT_DIR}/.env.example" "$LOCAL_ENV_FILE"
  upsert_env_file_value "$LOCAL_ENV_FILE" DOMAIN "$DOMAIN"
  upsert_env_file_value "$LOCAL_ENV_FILE" TRAEFIK_NETWORK "$TRAEFIK_NETWORK"
  scp -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" -q \
    "$LOCAL_ENV_FILE" "${DEPLOY_USER}@${SERVER}:${APP_DIR}/.env"
  ssh -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" "${DEPLOY_USER}@${SERVER}" \
    "chmod 600 '${APP_DIR}/.env'"
  ok ".env created with DOMAIN=${DOMAIN}"
fi

GENERATED_API_SECRET_KEY=""
if ssh -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" "${DEPLOY_USER}@${SERVER}" "[ -f '${APP_DIR}/app.env' ]"; then
  ok "${APP_DIR}/app.env already exists, leaving it alone"
else
  GENERATED_API_SECRET_KEY="$(openssl rand -hex 32)"
  cp "${SCRIPT_DIR}/app.env.example" "$LOCAL_APP_ENV_FILE"
  upsert_env_file_value "$LOCAL_APP_ENV_FILE" API_SECRET_KEY "$GENERATED_API_SECRET_KEY"
  scp -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" -q \
    "$LOCAL_APP_ENV_FILE" "${DEPLOY_USER}@${SERVER}:${APP_DIR}/app.env"
  ssh -i "$PRIVATE_KEY" "${SSH_BASE_OPTS[@]}" "${DEPLOY_USER}@${SERVER}" \
    "chmod 600 '${APP_DIR}/app.env'"
  ok "app.env created with a random API_SECRET_KEY"
fi

section "All done"

cat <<EOF

Next steps:

1. Fill runtime values on the server:
   ssh -i ${PRIVATE_KEY} ${DEPLOY_USER}@${SERVER}
   cd ${APP_DIR}
   editor app.env

2. Configure registry access for private images if needed:
   docker login <registry-host>

3. Optional GitHub Actions deploy example:
   copy deploy/vps-traefik/github-actions-deploy.yml.example
   to .github/workflows/deploy-vps-traefik.yml in a derived project.

Required production environment secrets:
  SERVER_HOST       ${SERVER}
  SERVER_USER       ${DEPLOY_USER}
  SERVER_SSH_KEY    full contents of ${PRIVATE_KEY}

Useful production environment variables:
  PRODUCTION_DOMAIN ${DOMAIN}
  PRODUCTION_APP_DIR ${APP_DIR}

EOF

if [[ -n "$GENERATED_API_SECRET_KEY" ]]; then
  cat <<EOF
Generated API_SECRET_KEY was written to ${APP_DIR}/app.env.
CD does not overwrite app.env.

EOF
fi
