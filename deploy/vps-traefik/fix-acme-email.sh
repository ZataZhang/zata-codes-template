#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# fix-acme-email.sh — one-shot repair for the "Traefik default cert" foot-gun.
#
# Symptom this fixes:
#   - Browser shows "此网站的证书无效" (or "Your connection is not private")
#   - `openssl s_client` reports issuer = "CN=TRAEFIK DEFAULT CERT"
#   - /opt/traefik/letsencrypt/acme.json does not exist
#
# Root cause:
#   The upstream install-docker-traefik.sh left a literal placeholder email
#   (typically "admin@example.com") hard-coded in /opt/traefik/traefik.yml.
#   Let's Encrypt silently rejects it on first contact, acme.json is never
#   created, and Traefik falls back to its built-in self-signed cert.
#
# This script:
#   1. Locates the Traefik install (looks at common paths).
#   2. Asks for a real email if the current one is a placeholder, or accepts
#      the existing one if it looks like a real mailbox.
#   3. Rewrites the `email:` line in traefik.yml.
#   4. Removes any stale acme.json so Traefik re-issues from scratch.
#   5. Restarts the Traefik container.
#   6. Polls the Traefik log for the new cert to appear (up to ~60s).
#
# Re-run safe: re-running is fine, the email prompt short-circuits if the
# current email already looks real.
#
# Usage:
#   sudo bash fix-acme-email.sh
#   sudo bash fix-acme-email.sh --email you@example.com   # skip the prompt
# -----------------------------------------------------------------------------
set -euo pipefail

EMAIL_FLAG=""
TRAEFIK_DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [--email you@example.com]

With no arguments, interactively prompts for an email. Pass --email to skip
the prompt (useful in scripts or when the placeholder is already known).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email) EMAIL_FLAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

bar()    { printf '\n\033[1;36m━━━ %s ━━━\033[0m\n' "$*"; }
info()   { printf '  \033[1;34m•\033[0m %s\n' "$*"; }
ok()     { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn()   { printf '  \033[1;33m!\033[0m %s\n' "$*"; }
fail()   { printf '  \033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# Pick up sudo when not root.
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else fail "Run as root or with sudo."; fi
else
  SUDO=""
fi

command -v docker >/dev/null 2>&1 || fail "docker not found in PATH"

# ---- Locate Traefik install --------------------------------------------------
bar "1. Locate Traefik install"
for candidate in /opt/traefik /root/traefik /home/*/traefik /etc/traefik; do
  for path in $candidate; do
    if [ -f "$path/traefik.yml" ]; then
      TRAEFIK_DIR="$path"
      break 2
    fi
  done
done
if [ -z "$TRAEFIK_DIR" ]; then
  fail "Could not find Traefik install. Set TRAEFIK_DIR manually and re-run."
fi
ok "TRAEFIK_DIR=$TRAEFIK_DIR"

# ---- Read current email -----------------------------------------------------
bar "2. Current ACME email"
CONFIG="$TRAEFIK_DIR/traefik.yml"
CURRENT_EMAIL=$($SUDO grep -E 'email:' "$CONFIG" 2>/dev/null \
  | head -1 | sed -n 's/.*email:[[:space:]]*"\([^"]*\)".*/\1/p')
if [ -z "$CURRENT_EMAIL" ]; then
  CURRENT_EMAIL=$($SUDO grep -E 'email:' "$CONFIG" 2>/dev/null \
    | head -1 | sed -n "s/.*email:[[:space:]]*'\([^']*\)'.*/\1/p")
fi
if [ -z "$CURRENT_EMAIL" ]; then
  CURRENT_EMAIL=$($SUDO grep -E 'email:' "$CONFIG" 2>/dev/null \
    | head -1 | sed -n 's/.*email:[[:space:]]*\(.*\)/\1/p' | tr -d '"' | tr -d "'" | tr -d ' ')
fi
info "Current email in traefik.yml: '${CURRENT_EMAIL:-<missing>}'"

# ---- Resolve which email to use --------------------------------------------
bar "3. Resolve target email"
PLACEHOLDER_RE='^(admin@example\.com|you@example\.com|example\.com|.*@example\.com|root@localhost|<missing>)?$'
if [[ -z "$EMAIL_FLAG" ]]; then
  if [[ "$CURRENT_EMAIL" =~ $PLACEHOLDER_RE ]] || [ -z "$CURRENT_EMAIL" ]; then
    printf '  Enter a real email for Let'"'"'s Encrypt registration: '
    IFS= read -r EMAIL_FLAG </dev/tty
    [ -z "$EMAIL_FLAG" ] && fail "Email cannot be empty."
  else
    info "Current email looks real; reusing it. Pass --email to override."
    EMAIL_FLAG="$CURRENT_EMAIL"
  fi
fi
# Basic sanity check: must contain @ and a dot in the domain part.
if ! printf '%s' "$EMAIL_FLAG" | grep -qE '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'; then
  fail "'$EMAIL_FLAG' is not a valid email address."
fi
ok "Target email: $EMAIL_FLAG"

# ---- Rewrite traefik.yml ----------------------------------------------------
bar "4. Rewrite $CONFIG"

# Replace any line that starts with optional whitespace then `email:` under
# certificatesResolvers.letsencrypt.acme — but only if it has a placeholder
# value. If the value already looks real, we still replace it to honor the
# user-provided --email.
$SUDO cp -a "$CONFIG" "${CONFIG}.bak.$(date +%s)"
info "Backed up to ${CONFIG}.bak.<timestamp>"

# Use a literal rewrite — quote the email as the original file did.
$SUDO sed -i -E "s|^([[:space:]]*email:[[:space:]]*\")[^\"]*(\".*)$|\1${EMAIL_FLAG}\2|" "$CONFIG"

NEW_EMAIL=$($SUDO grep -E 'email:' "$CONFIG" | head -1 | sed -n 's/.*email:[[:space:]]*"\([^"]*\)".*/\1/p')
if [ "$NEW_EMAIL" != "$EMAIL_FLAG" ]; then
  fail "Failed to rewrite email. Check $CONFIG manually."
fi
ok "traefik.yml updated: email = $NEW_EMAIL"

# ---- Remove stale acme.json -------------------------------------------------
bar "5. Clear stale acme.json"
ACME_PATH="$TRAEFIK_DIR/letsencrypt/acme.json"
# Detect any candidate file — script may have written elsewhere.
for candidate in \
    "$TRAEFIK_DIR/acme.json" \
    "$TRAEFIK_DIR/letsencrypt/acme.json" \
    "$TRAEFIK_DIR/dynamic/acme.json"; do
  if [ -f "$candidate" ]; then
    info "Removing stale $candidate"
    $SUDO rm -f "$candidate"
  fi
done

# ---- Restart Traefik --------------------------------------------------------
bar "6. Restart Traefik"
TRAEFIK_CID=$($SUDO docker ps -q --filter ancestor=traefik:v3.7 2>/dev/null | head -1)
if [ -z "$TRAEFIK_CID" ]; then
  TRAEFIK_CID=$($SUDO docker ps --format '{{.ID}} {{.Names}}' 2>/dev/null \
    | grep -i traefik | head -1 | awk '{print $1}')
fi
if [ -z "$TRAEFIK_CID" ]; then
  warn "Could not find a running Traefik container. Trying docker compose restart anyway."
  if [ -f "$TRAEFIK_DIR/docker-compose.yml" ]; then
    (cd "$TRAEFIK_DIR" && $SUDO docker compose restart traefik) || warn "compose restart failed"
  fi
else
  ok "Traefik container: $TRAEFIK_CID"
  $SUDO docker restart "$TRAEFIK_CID"
fi

# ---- Wait for cert issuance -------------------------------------------------
bar "7. Wait for cert issuance (up to 180s)"
ACME_FILE=""
for candidate in \
    "$TRAEFIK_DIR/acme.json" \
    "$TRAEFIK_DIR/letsencrypt/acme.json" \
    "$TRAEFIK_DIR/dynamic/acme.json"; do
  if [ -f "$candidate" ]; then
    ACME_FILE="$candidate"
    break
  fi
done

# The first cert is requested lazily on the first inbound HTTPS request for
# a domain that has no cert yet, so we make one ourselves to speed things up.
DOMAIN_HINT="${DOMAIN:-}"
if [ -n "$DOMAIN_HINT" ] && [ -n "$TRAEFIK_CID" ]; then
  info "Triggering a probe request to https://$DOMAIN_HINT to kick off ACME"
  curl -sk --max-time 5 "https://$DOMAIN_HINT/" -o /dev/null || true
fi

DEADLINE=$((SECONDS + 180))
while [ $SECONDS -lt $DEADLINE ]; do
  # Look in the most likely locations.
  for f in \
      "$TRAEFIK_DIR/acme.json" \
      "$TRAEFIK_DIR/letsencrypt/acme.json" \
      "$TRAEFIK_DIR/dynamic/acme.json"; do
    if [ -f "$f" ] && [ -s "$f" ]; then
      ACME_FILE="$f"
      # A real cert has nonzero Certificates list and a non-empty domain entry.
      if $SUDO python3 -c "
import json, sys
try:
  with open('$f') as fh: d = json.load(fh)
  le = d.get('letsencrypt', {})
  total = sum(len(acc.get('Certificates', [])) for acc in le.values() if isinstance(acc, dict))
  sys.exit(0 if total > 0 else 1)
except Exception: sys.exit(1)
" 2>/dev/null; then
        ok "Cert issued! Stored at $ACME_FILE"
        bar "Done"
        $SUDO ls -la "$ACME_FILE"
        info "You can verify with:"
        info "    echo | openssl s_client -connect <your-domain>:443 -servername <your-domain> 2>/dev/null \\"
        info "      | openssl x509 -noout -issuer -subject -dates"
        exit 0
      fi
    fi
  done
  sleep 5
done

warn "Cert did not appear within 60s. Check Traefik logs:"
[ -n "$TRAEFIK_CID" ] && info "    sudo docker logs --tail 200 $TRAEFIK_CID | grep -iE 'acme|certificate|error'"
exit 1
