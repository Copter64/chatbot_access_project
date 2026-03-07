#!/usr/bin/env bash
# deploy.sh — Bootstrap a fresh Ubuntu 24.04 VM as the gameserver-access-bot
# Docker host.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Copter64/chatbot_access_project/master/deploy.sh | bash
#   — or —
#   bash deploy.sh
#
# Run as a normal user with sudo privileges (NOT as root).
# ---------------------------------------------------------------------------

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO_URL="https://github.com/Copter64/chatbot_access_project.git"
INSTALL_DIR="$HOME/chatbot_access_project"
CERT_DOMAIN="home.chrissibiski.com"
CERT_DIR="/etc/letsencrypt/live/${CERT_DOMAIN}"

# ---------------------------------------------------------------------------
# 1. System update
# ---------------------------------------------------------------------------
info "Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ---------------------------------------------------------------------------
# 2. Install Docker
# ---------------------------------------------------------------------------
if command -v docker &>/dev/null; then
    info "Docker already installed: $(docker --version)"
else
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    info "Docker installed: $(docker --version)"
fi

# Add current user to docker group if not already there
if ! groups | grep -qw docker; then
    info "Adding $USER to the docker group..."
    sudo usermod -aG docker "$USER"
    warn "Group change takes effect on next login."
    warn "This script will use 'sudo docker' for the remainder of this run."
    DOCKER_CMD="sudo docker"
else
    DOCKER_CMD="docker"
fi

# ---------------------------------------------------------------------------
# 3. Install git & certbot
# ---------------------------------------------------------------------------
info "Installing git and certbot..."
sudo apt-get install -y -qq git certbot

# ---------------------------------------------------------------------------
# 4. Clone repository
# ---------------------------------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repository already exists at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull
else
    info "Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ---------------------------------------------------------------------------
# 5. Create data directory (SQLite DB + log file live here)
# ---------------------------------------------------------------------------
info "Creating data directory..."
mkdir -p data

# ---------------------------------------------------------------------------
# 6. TLS certificates
# ---------------------------------------------------------------------------
if [ -d "$CERT_DIR" ] && [ -f "$CERT_DIR/fullchain.pem" ]; then
    info "Let's Encrypt certs already present at $CERT_DIR"
else
    warn "TLS certs not found at $CERT_DIR"
    echo ""
    echo "  Choose how to obtain certs:"
    echo "  A) Copy from old host (you will be prompted for the old host IP/user)"
    echo "  B) Issue new cert via DNS challenge (requires domain DNS access)"
    echo "  S) Skip — I will handle certs manually"
    echo ""
    read -rp "  Choice [A/B/S]: " CERT_CHOICE

    case "${CERT_CHOICE^^}" in
        A)
            read -rp "  Old host user@IP (e.g. copter64@192.168.1.122): " OLD_HOST
            info "Copying certs from $OLD_HOST..."
            # shellcheck disable=SC2029
            ssh "$OLD_HOST" "sudo tar czf - /etc/letsencrypt" \
                | sudo tar xzf - -C /
            sudo chown -R root:"$USER" \
                /etc/letsencrypt/live /etc/letsencrypt/archive
            sudo chmod 750 \
                /etc/letsencrypt/live /etc/letsencrypt/archive
            sudo chmod 640 \
                "/etc/letsencrypt/archive/${CERT_DOMAIN}/"*.pem
            info "Certs copied successfully."
            ;;
        B)
            info "Requesting cert via DNS challenge..."
            sudo certbot certonly \
                --manual \
                --preferred-challenges dns \
                -d "$CERT_DOMAIN"
            ;;
        S)
            warn "Skipping cert setup. Set SSL_CERT and SSL_KEY in .env before starting."
            ;;
        *)
            warn "Unrecognised choice — skipping cert setup."
            ;;
    esac
fi

# Enable certbot auto-renewal timer
if systemctl list-units --type=service | grep -q "certbot"; then
    sudo systemctl enable --now certbot.timer 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# 7. Create .env if it doesn't exist
# ---------------------------------------------------------------------------
if [ -f ".env" ]; then
    info ".env already exists — skipping template creation."
else
    info "Creating .env from template..."
    cp .env.example .env

    warn "You must fill in .env before starting the container."
    warn "Opening .env in nano — save and exit when done."
    sleep 2
    nano .env
fi

# ---------------------------------------------------------------------------
# 8. Build Docker image
# ---------------------------------------------------------------------------
info "Building Docker image..."
$DOCKER_CMD compose build

# ---------------------------------------------------------------------------
# 9. Start the container
# ---------------------------------------------------------------------------
info "Starting container..."
$DOCKER_CMD compose up -d

# ---------------------------------------------------------------------------
# 10. Verify
# ---------------------------------------------------------------------------
info "Waiting 5 seconds for startup..."
sleep 5

WEB_PORT=$(grep -E "^WEB_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "8443")

echo ""
info "Container status:"
$DOCKER_CMD compose ps

echo ""
info "Health check: https://localhost:${WEB_PORT}/health"
HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" \
    "https://localhost:${WEB_PORT}/health" || echo "unreachable")

if [ "$HTTP_STATUS" = "200" ]; then
    info "Health check PASSED (HTTP 200)"
else
    warn "Health check returned: $HTTP_STATUS"
    warn "Check logs: docker compose logs -f bot"
fi

echo ""
echo "---------------------------------------------------------------------"
echo "  Deployment complete."
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f bot       # live logs"
echo "    docker compose restart bot       # restart"
echo "    docker compose down              # stop"
echo "    git pull && docker compose up -d --build  # update"
echo ""
echo "  Next step: update the UDM Pro port forward for port ${WEB_PORT}"
echo "  to point to this VM's LAN IP ($(hostname -I | awk '{print $1}'))"
echo "---------------------------------------------------------------------"
