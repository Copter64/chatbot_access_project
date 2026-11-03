#!/usr/bin/env bash
# acme_setup.sh -- one-shot, idempotent Let's Encrypt setup (DNS-01, Cloudflare).
#
# Usage:
#   scripts/acme_setup.sh DOMAIN
# DOMAIN may also come from the DOMAIN env var (arg wins if both are set).
#
# Optional env vars (defaults in parentheses):
#   CERT_HOME      ($HOME/.certbot-home)  user-owned certbot home;
#                 venv, credentials, config/work/logs all live under it.
#                 No root is required.
#   CF_TOKEN_FILE  ($HOME/.secrets/cf_dns_token)  file holding the
#                 Cloudflare API token; must be 0600. Never printed.
#   EMAIL          (unset) ACME account contact. Unset => register
#                 without an email address.
#
# Output contract:
#   success: exactly one stdout line
#     ACME_DONE certname=NAME certpath=/abs/path/fullchain.pem
#   failure: ACME_FAILED reason=SHORT  on stderr, exit 2
#
# Security: the token is read from CF_TOKEN_FILE via $(<file) -- never
# argv, never echoed, and the generated credentials file is chmod 600.

set -euo pipefail

usage() {
  echo "Usage: $0 DOMAIN   (or set DOMAIN and pass no args)" >&2
  echo "  Env: CERT_HOME, CF_TOKEN_FILE, EMAIL (see header for defaults)" >&2
  exit 2
}

fail() {
  echo "ACME_FAILED reason=$1" >&2
  exit 2
}

# Let's Encrypt does not issue for localhost or IP literals -- fail fast
# with a clear message instead of burning an ACME attempt on it.
validate_domain() {
  local domain=$1
  if [[ "$domain" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "ERROR: '$domain' is an IP literal. Let's Encrypt will not issue for it." >&2
    echo "       Use a real domain (Option B) or a self-signed cert (Option C, docs/SSL.md)." >&2
    fail "domain-not-issuable"
  fi
  case "$domain" in
    localhost|*.localhost|127.*|0.0.0.0)
      echo "ERROR: '$domain' is not a public DNS name. Let's Encrypt will not issue for it." >&2
      echo "       Use a real domain (Option B) or a self-signed cert (Option C, docs/SSL.md)." >&2
      fail "domain-not-issuable"
      ;;
  esac
}

ensure_dirs() {
  local cert_home=$1
  for d in "$cert_home/config" "$cert_home/work" "$cert_home/logs"; do
    install -d -m 755 "$d"
  done
}

# Load the Cloudflare token from CF_TOKEN_FILE into the 0600 credentials
# file certbot's cloudflare plugin expects. Token travels via $(<file),
# never argv, never printed.
write_credentials() {
  local cert_home=$1 token_file=$2 cred_file
  cred_file="$cert_home/cf_dns.ini"
  [[ -f "$token_file" ]] || fail "cf-token-file-missing"
  local perms
  perms=$(stat -c %a "$token_file")
  if [[ "$perms" != "600" ]]; then
    echo "ERROR: $token_file is mode $perms; expected 600. Fix: chmod 600 $token_file" >&2
    fail "cf-token-file-perms"
  fi
  local token
  token=$(<"$token_file")
  [[ -n "$token" ]] || fail "cf-token-empty"
  printf 'dns_cloudflare_api_token = %s\n' "$token" > "$cred_file"
  chmod 600 "$cred_file"
}

create_venv() {
  local cert_home=$1
  install -d "$cert_home/venv" 2>/dev/null || true
  if [[ ! -x "$cert_home/venv/bin/python" ]]; then
    echo "Creating venv at $cert_home/venv (first run)" >&2
    python3 -m venv "$cert_home/venv"
  fi
  if ! "$cert_home/venv/bin/python" -c 'import certbot; import certbot_dns_cloudflare' 2>/dev/null; then
    echo "Installing certbot + certbot-dns-cloudflare (first run)" >&2
    "$cert_home/venv/bin/python" -m pip install --quiet --upgrade pip
    "$cert_home/venv/bin/python" -m pip install --quiet --upgrade \
      'certbot>=2,<3' 'certbot-dns-cloudflare>=2,<3'
  fi
}

sanitized_name() {
  local domain=$1
  echo "${domain//./-}"
}

main() {
  local domain
  if [[ $# -ge 1 ]]; then
    domain="${1}"
  else
    domain="${DOMAIN:-}"
  fi
  if [[ -z "$domain" ]]; then
    usage
  fi

  validate_domain "$domain"

  local cert_home="${CERT_HOME:-$HOME/.certbot-home}"
  local token_file="${CF_TOKEN_FILE:-$HOME/.secrets/cf_dns_token}"
  local email="${EMAIL:-}"
  local name
  name=$(sanitized_name "$domain")

  ensure_dirs "$cert_home"
  write_credentials "$cert_home" "$token_file"
  create_venv "$cert_home"

  local certbot="$cert_home/venv/bin/certbot"
  local flags
  flags=(
    --config-dir "$cert_home/config"
    --work-dir "$cert_home/work"
    --logs-dir "$cert_home/logs"
    --non-interactive --agree-tos
    --cert-name "$name"
  )

  # Idempotency: is there already a cert for this name under this home?
  local existing
  existing=$("$certbot" certificates 2>/dev/null | grep -c "Certificate Name: $name\b" || true)

  if [[ "$existing" -ge 1 ]]; then
    echo "Renewing existing certificate $name" >&2
    "$certbot" renew "${flags[@]}"
  else
    echo "Issuing new certificate for $domain" >&2
    local email_args=()
    if [[ -n "$email" ]]; then
      email_args=(--email "$email")
    else
      email_args=(--register-unsafely-without-email)
    fi
    "$certbot" certonly \
      --dns-cloudflare \
      --dns-cloudflare-credentials "$cert_home/cf_dns.ini" \
      --dns-cloudflare-propagation-seconds 60 \
      --domain "$domain" \
      "${flags[@]}" \
      "${email_args[@]}" \
      || fail "issuance-failed"
  fi

  # certbot live layout: <config-dir>/live/<name>/fullchain.pem
  local fullchain="$cert_home/config/live/$name/fullchain.pem"
  if [[ ! -f "$fullchain" ]]; then
    fail "fullchain-missing"
  fi
  echo "ACME_DONE certname=$name certpath=$(readlink -f "$fullchain")"
}

main "$@"
