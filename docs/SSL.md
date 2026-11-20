# SSL / TLS for the IP-Capture Web Service

This document covers every supported way to run the web frontend
(Flask, the `/request-access` IP-capture flow) with or without TLS,
how to automate Let's Encrypt renewal without root, and how to roll
back. Read top-to-bottom for a fresh deployment; jump to the
troubleshooting table if something goes sideways on an existing one.

---

## 1. Deciding which option to use

The code (`web/ssl.py`, consumed from `web/app.py`) reads two
settings: `SSL_CERT` and `SSL_KEY`. The combination decides the mode:

| `SSL_CERT` | `SSL_KEY` | Result at boot |
|---|---|---|
| unset | unset | **Option A** -- plain HTTP. A warning is logged. Legal for LAN/dev. |
| set | set | TLS on. Pair loaded into an `ssl.SSLContext` via `load_cert_chain`. |
| set | **unset** | **Hard boot failure** (`web.ssl.ConfigError`). |
| **unset** | set | **Hard boot failure** (`web.ssl.ConfigError`). |

The half-configured states fail **on purpose**: a typo or a
half-rolled-out renewal must not silently serve the IP-capture form
over cleartext. If you see ``ConfigError: Half-configured TLS...`` in
the logs, the fix is "set both" or "unset both" -- there is no third
state.

Cert expiry is **reported, not enforced**: `expiry_days_remaining()`
is logged at boot, so a renewal hiccup does not kill the service
mid-renewal. The `scripts/cert_health_check.sh` probe is what turns
"about to expire" into an alert you can act on.

### Decision tree

```
Is the host reachable from the internet?
+-- NO (LAN, home network, dev box)
|   +-- Option A -- no cert. Both vars blank. Done.
+-- YES
    Do you have API access to the zone's DNS?
    +-- YES (e.g. domain on Cloudflare)
    |   +-- Option B -- Let's Encrypt DNS-01. RECOMMENDED.
    |        No port 80 needed; works behind a router exposing only
    |        :443. This is the default path for public deployments.
    +-- NO, but you can open port 80
    |   +-- Option B' -- Let's Encrypt HTTP-01. Something must answer
    |        on port 80 at /.well-known/acme-challenge/... .
    |        (The reference deployment could not use this: a
    |        2026-11-03 `ss -tln` audit showed only :22 and :8443
    |        listening on that host.)
    +-- NO, and you have another certificate source anyway
        +-- Option C -- your own certificate. Corporate CA, AWS ACM
             (export the PEMs), ZeroSSL, or self-signed for setups
             that trust it. Any PEM cert + matching PEM key works.
```

| | Option A | Option B (DNS-01) | Option B' (HTTP-01) | Option C |
|---|---|---|---|---|
| Internet-safe | **No** | Yes | Yes | Yes (if CA trusted) |
| Port 80 required | No | **No** | Yes | No |
| Root on host | No | **No (user venv)** | varies | No |
| Auto-renewal | n/a | certbot + repo hook | certbot + repo hook | provider-specific |
| Extra secret needed | none | one DNS API token | none | provider's |

---

## 2. Option A -- no certificate (plain HTTP)

**When:** the IP-capture page is only ever opened from the LAN; you are
developing; the host is not NAT-mapped for web traffic.

The code already supports this -- it is the shipped default in
`.env.example` and requires zero setup:

```bash
# .env -- both blank (the default)
SSL_CERT=
SSL_KEY=
```

Boot the container as usual. Expect this startup warning:

```
WARNING web.ssl: SSL_CERT/SSL_KEY unset -- serving plain HTTP.
```

That warning is the point: do not put a plain-HTTP instance behind a
public URL, because the access tokens and IPs in the form travel
cleartext.

**Rolling back to Option A later:** blank out both vars (in `.env` or
the compose env), `docker compose up -d`, done. Keep the cert files on
disk -- they are small, and re-enabling is a two-line change.

---

## 3. Option B -- Let's Encrypt DNS-01 via Cloudflare (recommended)

Two properties make this the least-fragile path:

1. **No port-80 dependency.** Validation is a `_acme-challenge` TXT
   record for your domain, added and removed automatically during each
   issuance/renewal (typically 30-60 seconds; nothing accumulates).
   Router/firewall only ever needs :443.
2. **No root needed.** Everything lives in a user-owned `CERT_HOME`
   (default `~/.certbot-home`) with a Python venv, so a normal account
   with `docker` group access is sufficient on the bot host.

### 3.1 Prerequisites (once)

- A domain you control, zone NS at Cloudflare (the reference deployment:
  `chrissibiski.com` on `noor.ns.cloudflare.com`).
- One Cloudflare API token scoped to that zone with **Zone DNS: Edit**.
  Create it at *Cloudflare dashboard -> API Tokens -> Create Token ->
  Edit zone DNS*. Scope: that one zone, DNS only. **Never paste the
  token into chat, a log, or a PR** (Hard rules, section 7).
- `openssl`, `python3` (>= 3.8) and `docker` on the bot host (all
  present on the reference deployment).

### 3.2 Store the token safely

On the bot host, as the normal user:

```bash
umask 077
mkdir -p ~/.secrets
# Read the token interactively so it never lands in history or logs.
read -r -s -p "Cloudflare DNS token: " TOKEN
printf '%s\n' "$TOKEN" > ~/.secrets/cf_dns_token
unset TOKEN
chmod 600 ~/.secrets/cf_dns_token
ls -l ~/.secrets/cf_dns_token   # -rw------- is the state you want
```

`scripts/acme_setup.sh` refuses to run if that file is missing or not
`0600`, and no script in this repo prints the token value.

### 3.3 Issue (or renew) the certificate

From a checkout of this repo (or a copy of `scripts/`):

```bash
scripts/acme_setup.sh home.example.com
```

It is idempotent -- safe to run today and to re-run in six months.
Order of operations:

1. Refuses `localhost` / IP-literal domains loudly (Let's Encrypt does
   not issue for them -- use Option C for those).
2. First run only: creates `~/.certbot-home/venv` with `certbot` (2.x)
   and `certbot-dns-cloudflare`; skipped when already importable.
3. Copies the token into `~/.certbot-home/cf_dns.ini` (mode `0600`) in
   plugin format (`dns_cloudflare_api_token = ...`), reading it from
   `CF_TOKEN_FILE` via command substitution -- never argv, never logs.
4. If a certificate for the name already exists under this `CERT_HOME`:
   `certbot renew --cert-name <name>` (idempotency path). Otherwise
   `certbot certonly --dns-cloudflare ...`.
5. On success prints exactly one stdout line:

   ```
   ACME_DONE certname=home-example-com \
     certpath=<CERT_HOME>/config/live/home-example-com/fullchain.pem
   ```

   On failure: last stderr line `ACME_FAILED reason=<short>`, exit 2.

Optional overrides:

| Var | Default | Purpose |
|---|---|---|
| `CERT_HOME` | `$HOME/.certbot-home` | User-owned certbot home (config/work/logs/venv). |
| `CF_TOKEN_FILE` | `$HOME/.secrets/cf_dns_token` | File holding the token; must be `0600`. |
| `EMAIL` | *(unset)* | ACME account contact; unset registers without email. |

Layout after a successful run (defaults):

```
~/.certbot-home/
+-- venv/                    # certbot + cloudflare plugin
+-- cf_dns.ini               # 0600 -- never commit, never print
+-- config/live/<name>/      # fullchain.pem, privkey.pem (the live pair)
+-- config/renewal/          # account + renewal state
+-- work/
+-- logs/
+-- renewal-hooks/deploy/    # <- wire on_renew.sh here (3.5)
```

`<name>` is the domain with dots turned into dashes
(`home.example.com` -> `home-example-com`).

### 3.4 Point the bot at the certificate

**Layout 1 -- mount the host cert dir read-only (simplest).**
`docker-compose.yml`:

```yaml
services:
  bot:
    # ...existing image/env...
    volumes:
      - ./data:/app/data
      # NEW, read-only:
      - ${HOME}/.certbot-home/config/live/home-example-com:/etc/tls-live:ro
    environment:
      # ...existing env...
      SSL_CERT=/etc/tls-live/fullchain.pem
      SSL_KEY=/etc/tls-live/privkey.pem
```

> **`${HOME}` caveat:** Docker Compose interpolates `${HOME}` from the
> *host shell* running it. Launch `docker compose up` from a login
> shell (or hard-code the absolute path in the file) and the mount is
> correct. The historical mount on the reference host was
> `/etc/letsencrypt:/etc/letsencrypt:ro` (root-owned) -- the layout
> above replaces it, so the renewal flow never needs root again.

**Layout 2 -- stable `~/.tls-live` copy (recommended when the bot runs
in Docker).** `scripts/on_renew.sh` maintains this directory: after
each renewal it copies the fresh `fullchain.pem` + `privkey.pem` there
(cert `0644`, key `0600`, parent `0755`) and restarts the container.
Compose side:

```yaml
    volumes:
      - ./data:/app/data
      - ${HOME}/tls-live:/etc/tls-live:ro
    environment:
      SSL_CERT=/etc/tls-live/fullchain.pem
      SSL_KEY=/etc/tls-live/privkey.pem
```

Layout 2 decouples the container from certbot's internals: you can
delete and recreate `CERT_HOME` and the running bot never blinks --
the live pair keeps being served from `~/.tls-live`.

### 3.5 Wire up renewal automation

Certbot renews automatically (the `certbot` venv timer, or a crontab
entry) and then runs every script in its deploy-hooks dir. Because we
use a user-owned `CERT_HOME`, that dir is:

```
$CERT_HOME/renewal-hooks/deploy/
```

Register the hook once:

```bash
CERT_HOME=${CERT_HOME:-$HOME/.certbot-home}
mkdir -p "$CERT_HOME/renewal-hooks/deploy"
chmod 755  "$CERT_HOME/renewal-hooks/deploy"
ln -s /abs/path/to/repo/scripts/on_renew.sh \
      "$CERT_HOME/renewal-hooks/deploy/on_renew.sh"
ls -l "$CERT_HOME/renewal-hooks/deploy"
```

What happens on each renewal:

1. certbot issues/updates the cert under `CERT_HOME/config/...`.
2. `on_renew.sh` runs with `CERT_PATH`/`KEY_PATH` supplied by certbot;
   it copies the pair into `BOT_CERT_DIR` (default `~/.tls-live`)
   with the correct permissions and restarts `BOT_NAME`
   (default `gameserver-access-bot`), then verifies.
3. Final output line:
   `RENEW_DONE certname=<name> container=<name> date=<notAfter|unknown>`.
   Any failure: `RENEW_FAILED reason=<short>`, exit 2.

Environment the hook reads (defaults shown; these are consumed by the
script at runtime, **not** loaded from the bot's `.env`):

| Var | Default | Purpose |
|---|---|---|
| `BOT_CERT_DIR` | `$HOME/tls-live` | Where the live fullchain.pem/privkey.pem are copied. |
| `BOT_NAME` | `gameserver-access-bot` | Container to restart after the copy. |
| `RELOAD_WAIT_SECONDS` | `15` | Max wait for the container to report running. |
| `WEB_PORT` | `8443` | Port for the `openssl s_client` verification (when `DOMAIN` set). |
| `DOMAIN` | *(unset)* | When set, verifies the *served* cert is >= 30 days fresh. |

Renewal trigger. Either the certbot systemd timer (if you run certbot
as a service) or a user crontab entry:

```cron
# User crontab on the bot host (certbot runs from its own venv):
0 */12 * * * C=$HOME/.certbot-home; $C/venv/bin/certbot renew \
    --config-dir $C/config --work-dir $C/work --logs-dir $C/logs --quiet
```

And the weekly belt-and-braces health probe (Sunday 03:15, warns at
90 days out -- pointing at the `~/.tls-live` pair if you use Layout 2):

```cron
15 3 * * 0 scripts/cert_health_check.sh $HOME/.tls-live/fullchain.pem 90
```

Replace that path with `$HOME/.certbot-home/config/live/<name>/fullchain.pem`
if you use Layout 1 instead.

---

## 4. Option B (prime) -- Let's Encrypt, HTTP-01

Viable only if port 80 is reachable **and** something answers the
challenge path during issuance/renewal. The reference deployment could
not use this: a 2026-11-03 `ss -tln` audit showed only `:22` and
`:8443` listening, so DNS-01 was chosen instead. If your situation has
port 80 open, HTTP-01 avoids needing a DNS API token.

Differences vs Option B in this repo:

- `acme_setup.sh` is written for DNS-01. For HTTP-01, run certbot
  from the same venv but drop `--dns-cloudflare*` and add `--standalone`
  (or `--webroot -w <dir>` if your webroot is on this host):

  ```bash
  ~/.certbot-home/venv/bin/certbot certonly --standalone \
    --config-dir ~/.certbot-home/config \
    --work-dir  ~/.certbot-home/work \
    --logs-dir  ~/.certbot-home/logs \
    --domain home.example.com --non-interactive \
    --register-unsafely-without-email
  ```

- During renewal, whatever serves port 80 **must stay up and answer
  the challenge while the bot container restarts** -- a classic
  chicken-and-egg if the bot *itself* is the port-80 server.
  DNS-01 has no such coupling, which is why it is the recommendation.
- `on_renew.sh` and the health probe work unchanged (they only care
  about the resulting PEM pair).

If you end up closing port 80 later: switch back to DNS-01 (Option B),
not the other way around -- DNS-01 is strictly less fragile.

---

## 5. Option C -- your own certificate

Any PEM certificate plus its matching PEM private key works, because
`web/ssl.py` goes straight to `ssl.SSLContext.load_cert_chain`:

- Corporate / internal CA certificate (most intranet cases)
- AWS Certificate Manager -- export as PEM pair, paste into files
- ZeroSSL, Sectigo, or your other external CA
- Self-signed (trusted only on machines that trust your root;
  fine for internal tools with pre-provisioned trust)

### 5.1 Prepare the pair on the host

```bash
# Example: drop whatever your CA gave you into ~/.tls-live
mkdir -p ~/.tls-live
cp /some/path/your.fullchain.pem ~/.tls-live/fullchain.pem
cp /some/path/your.key.pem      ~/.tls-live/privkey.pem
chmod 755 ~/.tls-live
chmod 644 ~/.tls-live/fullchain.pem
chmod 600 ~/.tls-live/privkey.pem
```

Verify the pair actually matches **before** pointing the bot at it:

```bash
# The two digests MUST be identical.
openssl x509 -noout -modulus -in ~/.tls-live/fullchain.pem | openssl sha256
openssl rsa  -noout -modulus -in ~/.tls-live/privkey.pem   | openssl sha256
```

If they differ, you have a cert/key mismatch -- the bot will fail to
load them (see Troubleshooting).

### 5.2 Point the bot at it

Compose (same shape as Layout 2 in 3.4):

```yaml
    volumes:
      - ./data:/app/data
      - ${HOME}/tls-live:/etc/tls-live:ro
    environment:
      SSL_CERT=/etc/tls-live/fullchain.pem
      SSL_KEY=/etc/tls-live/privkey.pem
```

Bare-metal (no docker):

```bash
export SSL_CERT=$HOME/.tls-live/fullchain.pem
export SSL_KEY=$HOME/.tls-live/privkey.pem
python main.py
```

### 5.3 Renewal for Option C

Whatever produced the cert is responsible for renewing it (your
corporate PKI, the CA's portal, a script of your own). Two practical
choices:

1. **Manual refresh:** when you receive a new PEM pair, drop it into
   `~/.tls-live/`, then `docker compose restart bot` (or send the
   container a SIGHUP if you add one).
2. **Automate the copy:** point your CA's renewal step at the same
   `on_renew.sh` hook by exporting `CERT_PATH`/`KEY_PATH` before
   invoking it:

   ```bash
   CERT_PATH=/new/fullchain.pem KEY_PATH=/new/privkey.pem \
   BOT_NAME=gameserver-access-bot \
   scripts/on_renew.sh
   ```

   The `docker restart` + wait-for-running + optional `DOMAIN`
   verification all still apply identically.

The health probe works unchanged:

```bash
scripts/cert_health_check.sh ~/.tls-live/fullchain.pem 90
```

---
## 6. Troubleshooting

**"certificate expired" in the client**. The cert's `notAfter` is in
the past (the reference host had a Let's Encrypt E8 cert issued
2026-03-05 and expired 2026-06-03 before this work). Re-issue: Option B
means re-run `scripts/acme_setup.sh <domain>`; Option C means obtain a
fresh pair from your CA. Then restart the container.

**Bot fails to boot with `ConfigError: Half-configured TLS`**. Exactly
one of `SSL_CERT` / `SSL_KEY` is set -- a partial edit to `.env`. Set
both or blank both. There is no third state; the loud boot failure is
the feature.

**Boot SSLError / `load_cert_chain` error -- cert and key mismatch**.
Two different key pairs were mixed together. Compare:

```bash
openssl x509 -noout -modulus -in fullchain.pem | openssl sha256
openssl rsa  -noout -modulus -in privkey.pem   | openssl sha256
```

The two digests must be identical. If not, regenerate or re-fetch the
matching pair.

**`openssl rsa -noout -check` fails on `privkey.pem`**. The key carries
a passphrase (or is not PEM). Regenerate without a passphrase; a
passphrased key blocks non-interactive boot.

**`acme_setup.sh` exits 2: "domain not issuable"**. You passed
`localhost` or an IP literal. Let's Encrypt does not issue for those;
use a real DNS name (Option B) or self-sign (Option C).

**`acme_setup.sh` auth error from Cloudflare**. The token's scope does
not cover this zone (it may be valid for a different one), or the token
was revoked. Mint a fresh token scoped to the correct zone with
*Zone DNS: Edit*, replace the file at `CF_TOKEN_FILE` (keep `0600`),
re-run `acme_setup.sh` so the new token lands in the credentials file.

**Container restarts but still serves the old cert**. The new pair was
not actually picked up. `docker restart <BOT_NAME>` and verify with:

```bash
openssl s_client -connect <host>:8443 -servername <host> </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

**Health probe fails but the cert is fine on a browser**. The host
clock is skewed (the probe computes remaining days locally).
`timedatectl`; install/verify `chrony`.

**HTTP-01 broke after port 80 was closed by a firewall change**.
Renewal can no longer be validated. Switch to DNS-01 (Option B) --
strictly less fragile, no port dependency.

**`acme_setup.sh` refuses: `cf-token-file-perms`**. `CF_TOKEN_FILE` is
group/world readable. `chmod 600` it and re-run; the script refuses on
purpose.

**Renewal hook succeeded but the bot is not back up**. The container
crashed on boot (bad pair, `ConfigError`, etc.). `docker logs
<BOT_NAME> --tail 100`; usually a mismatch above or a `.env` edit.

---

## 7. Hard rules

- **Never paste the Cloudflare token (or any PEM key)** into chat, a
  log, a PR, or a commit. `~/.secrets/` (or equivalent) is its only home.
- **Set `SSL_CERT` and `SSL_KEY` together, or set neither.**
  `web/ssl.py` enforces this at boot; the loud failure is the feature.
- **Rotate the DNS token periodically.** A leaked token lets a holder
  add/remove DNS records in that zone (more with a mis-scoped one).
- **Keep one stable host path for the live pair** (e.g. `~/.tls-live`),
  mounted read-only into the container. Two live paths with the bot
  reading neither is a classic mid-migration breakage.
- **A cert is only as good as its renewal automation.** Before calling
  this done, confirm the renewal trigger (certbot timer/cron) **and**
  the deploy hook (`on_renew.sh`) are actually running on the host.

---

## 8. Rollback per option

**Option A (plain HTTP) -- the universal fallback.** Blank both
`SSL_CERT` and `SSL_KEY`, `docker compose up -d`. The bot serves
cleartext again and the IP-capture form works; the browser no longer
needs server-side TLS trust. Keep the PEM files on disk -- re-enabling
is a two-line change.

**Option B / B' -- roll back to A**, then separately decide whether to
re-attempt issuance (`acme_setup.sh <domain>`) or switch to C (your own
CA). There is no partial TLS state the code will accept.

**Option C -- roll back to A** if the CA pair stops working, or swap
in a fresh pair from the same CA. The compose volume path does not
change.

---

## 9. Files shipped with this PR

| Path | Purpose |
|---|---|
| `web/ssl.py` | TLS-mode resolver: plain HTTP, TLS on, or `ConfigError` when
half-configured. Logs days remaining. |
| `web/app.py` | Booted through `build_ssl_context(...)` instead of a raw `ssl.SSLContext`. |
| `tests/test_ssl.py` | Unit tests for all three states, mismatch, and the expiry helper. |
| `tests/conftest.py` | Self-contained session fixtures (valid / soon / mismatch pairs). |
| `scripts/acme_setup.sh` | One-shot, idempotent issue-or-renew (DNS-01,
Cloudflare; user venv, no root). |
| `scripts/on_renew.sh` | certbot deploy hook: copy live pair, restart container, verify. |
| `scripts/cert_health_check.sh` | Exit-code probe for cron/CI with
optional best-effort webhook alert. |
| `.env.example` | TLS section: three options, default (A) with both vars blank. |
| `docs/SSL.md` | This document. |
