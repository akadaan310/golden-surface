#!/bin/bash
# Installs/refreshes all Golden Surface units. Safe to re-run.
set -e
cd "$(dirname "$0")"
sudo cp golden-*.service /etc/systemd/system/
sudo systemctl daemon-reload
for u in golden-*.service; do sudo systemctl enable "$u" >/dev/null 2>&1; sudo systemctl restart "$u"; done
systemctl --no-pager --plain list-units 'golden-*'
