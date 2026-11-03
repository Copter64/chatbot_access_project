#!/usr/bin/env bash
set -euo pipefail

MIN_DAYS="${MIN_DAYS:-30}"
WEBHOOK_URL="${CERT_ALERT_WEBHOOK_URL:-}"

print_error() {
  echo "$1" >&2
}

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 CERT_FILE [MIN_DAYS]" >&2
  exit 2
fi
CERT_FILE="$1"
if [[ $# -ge 2 ]]; then
  MIN_DAYS="$2"
fi

if ! enddate=$(openssl x509 -enddate -noout -in "$CERT_FILE" 2>/dev/null); then
  print_error "HEALTH_CHECK_FAILED reason=parse"
  exit 2
fi
not_after=$(echo "$enddate" | cut -d= -f2)
not_after_ts=$(date -d "$not_after" +%s 2>/dev/null) || {
  print_error "HEALTH_CHECK_FAILED reason=parse"
  exit 2
}
now_ts=$(date +%s)
remaining_days=$(( (not_after_ts - now_ts) / 86400 ))

# Best-effort alert; a webhook failure must NOT change the exit code, and
# the URL is only ever passed as argv -- never interpolated or echoed.
fire_alert() {
  local url=$1
  if command -v curl >/dev/null 2>&1; then
    curl -s -X POST -H "Content-Type: application/json" \
      -d "{\"remaining_days\":$remaining_days}" "$url" >/dev/null 2>&1 || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$url" "$remaining_days" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
sys.exit(2) if not urllib.request.urlopen(
    sys.argv[1],
    data=json.dumps({"remaining_days": int(sys.argv[2])}).encode(),
    timeout=10,
).read() else None
PY
  fi
}

if (( remaining_days < MIN_DAYS )); then
  print_error "HEALTH_CHECK_FAILED remaining_days=$remaining_days"
  [[ -n "$WEBHOOK_URL" ]] && fire_alert "$WEBHOOK_URL"
  exit 2
else
  echo "HEALTH_CHECK_OK remaining_days=$remaining_days"
  exit 0
fi
