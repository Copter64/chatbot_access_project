#!/usr/bin/env bash
# on_renew.sh -- certbot renewal deploy hook for the bot's live cert pair.
#
# Invoked by certbot after a successful renewal; certbot passes CERT_PATH,
# KEY_PATH (plus DOMAIN, EXPIRATION) in the hook environment. Safe to run
# by hand for testing: provide CERT_PATH+KEY_PATH manually, or run with
# neither -- the live copy is then left untouched (NO_CERT_INPUT, exit 2),
# so this hook is non-destructive by default.
#
# Output contract (one final stdout line; progress on stderr):
#   success: RENEW_DONE certname=<name> container=<BOT_NAME> date=<ISO|unknown>
#   failure: RENEW_FAILED reason=<SHORT> on stderr, exit 2
#   no input: NO_CERT_INPUT on stderr, exit 2
#
# Security: never prints cert/key file contents. Idempotent.

set -euo pipefail

BOT_CERT_DIR="${BOT_CERT_DIR:-$HOME/tls-live}"
BOT_NAME="${BOT_NAME:-gameserver-access-bot}"
RELOAD_WAIT_SECONDS="${RELOAD_WAIT_SECONDS:-15}"
WEB_PORT="${WEB_PORT:-8443}"
DOMAIN="${DOMAIN:-}"
CERT_NAME="${CERT_NAME:-}"

fail() {
  echo "RENEW_FAILED reason=$1" >&2
  exit 2
}

copy_certs() {
  # Overwrite the live pair each run. 0644 cert / 0600 key / 0755 parent.
  mkdir -p -- "$BOT_CERT_DIR"
  chmod 755 -- "$BOT_CERT_DIR"
  cp -f -- "$CERT_PATH" "$BOT_CERT_DIR/fullchain.pem"
  chmod 644 -- "$BOT_CERT_DIR/fullchain.pem"
  cp -f -- "$KEY_PATH" "$BOT_CERT_DIR/privkey.pem"
  chmod 600 -- "$BOT_CERT_DIR/privkey.pem"
}

wait_for_running() {
  local container=$1 max_wait=$2 elapsed=0
  while true; do
    local status
    status=$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || echo "false")
    if [[ "$status" == "true" ]]; then
      return 0
    fi
    elapsed=$((elapsed + 1))
    if (( elapsed > max_wait )); then
      return 1
    fi
    sleep 1
  done
}

# Verify the served cert is fresh via openssl s_client.
assert_domain() {
  local domain=$1 web_port=$2
  local result not_after not_after_ts now_ts days_ahead
  result=$(openssl s_client -connect "${domain}:${web_port}" -servername "$domain" \
    < /dev/null 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
  if [[ -z "$result" ]]; then
    fail "verification-unreachable"
  fi
  not_after=$(grep '^notAfter=' <<< "$result" | cut -d= -f2-)
  not_after_ts=$(date -d "$not_after" +%s 2>/dev/null) || fail "expiry-parse"
  now_ts=$(date +%s)
  days_ahead=$(( (not_after_ts - now_ts) / 86400 ))
  if (( days_ahead < 30 )); then
    fail "expiry"
  fi
  echo "RENEW_DONE certname=${CERT_NAME:-$domain} container=$BOT_NAME date=$not_after"
}

main() {
  local certname_out="${CERT_NAME:-unknown}"

  # No input at all: non-destructive no-op for manual/testing runs.
  if [[ -z "${CERT_PATH:-}" && -z "${KEY_PATH:-}" ]]; then
    echo "NO_CERT_INPUT" >&2
    exit 2
  fi

  # Both must be present when either is.
  if [[ -z "${CERT_PATH:-}" || -z "${KEY_PATH:-}" ]]; then
    fail "missing-cert-or-key"
  fi
  [[ -f "$CERT_PATH" ]] || fail "cert-file-missing"
  [[ -f "$KEY_PATH" ]] || fail "key-file-missing"

  copy_certs

  # Restart the container only when it actually exists.
  if command -v docker >/dev/null 2>&1 && \
     docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$BOT_NAME"; then
    docker restart "$BOT_NAME" >&2
    wait_for_running "$BOT_NAME" "$RELOAD_WAIT_SECONDS" || fail "timeout"
  else
    echo "Container '$BOT_NAME' not found (or no docker) -- skipping restart." >&2
  fi

  # Final assertion.
  if [[ -n "$DOMAIN" ]]; then
    assert_domain "$DOMAIN" "$WEB_PORT"
  else
    # Domain not given: the on-disk pair must parse (key check best-effort).
    if ! openssl x509 -noout -subject -in "$BOT_CERT_DIR/fullchain.pem" >/dev/null 2>&1; then
      fail "cert-parse"
    fi
    if ! openssl pkey -noout -in "$BOT_CERT_DIR/privkey.pem" >/dev/null 2>&1; then
      echo "KEY_CHECK_WARN: privkey parse failed (passphrase or format)." >&2
    fi
    local enddate not_after
    enddate=$(openssl x509 -enddate -noout -in "$BOT_CERT_DIR/fullchain.pem" 2>/dev/null) || true
    not_after=$(grep '^notAfter=' <<< "${enddate:-}" | cut -d= -f2-) || true
    echo "RENEW_DONE certname=$certname_out container=$BOT_NAME date=${not_after:-unknown}"
  fi
}

main "$@"
