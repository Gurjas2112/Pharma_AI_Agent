#!/bin/bash
# EC2 user-data for the Ollama GPU host (Ubuntu 22.04 Deep Learning AMI, g4dn.xlarge / T4 16GB).
# Installs Ollama + Caddy bearer-token proxy with automatic TLS (sslip.io hostname).
set -euxo pipefail
TOKEN="__OLLAMA_PROXY_TOKEN__"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo 127.0.0.1)
SITE="${PUBLIC_IP//./-}.sslip.io"

curl -fsSL https://ollama.com/install.sh | sh
mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/override.conf <<CONF
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_FLASH_ATTENTION=1"
CONF
systemctl daemon-reload && systemctl enable --now ollama
for m in qwen2.5:7b-instruct qwen2.5:3b-instruct nomic-embed-text; do ollama pull "$m"; done

apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
apt-get update && apt-get install -y caddy
cat >/etc/caddy/Caddyfile <<CADDY
$SITE {
  @authorized header Authorization "Bearer $TOKEN"
  handle @authorized {
    reverse_proxy 127.0.0.1:11434 {
      header_up Host {upstream_hostport}
      flush_interval -1
    }
  }
  handle /healthz { respond "ok" 200 }
  handle { respond "unauthorized" 401 }
}
CADDY
systemctl restart caddy
echo "OLLAMA_BASE_URL=https://$SITE" > /etc/repurpora-endpoint
