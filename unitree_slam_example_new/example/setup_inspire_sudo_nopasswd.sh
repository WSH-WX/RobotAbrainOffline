#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-$(id -un)}"
INSPIRE_BIN="/mnt/ssd/navgation/projects/dfx_inspire_service/build/inspire_g1"
SUDOERS_FILE="/etc/sudoers.d/inspire_g1_nopasswd"
RULE_LINE="$TARGET_USER ALL=(root) NOPASSWD: $INSPIRE_BIN"

if [[ ! -x "$INSPIRE_BIN" ]]; then
  echo "Missing executable: $INSPIRE_BIN"
  exit 1
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

printf '%s\n' "$RULE_LINE" > "$tmp_file"
chmod 0440 "$tmp_file"

echo "Installing sudoers rule to: $SUDOERS_FILE"
sudo install -m 0440 "$tmp_file" "$SUDOERS_FILE"
sudo visudo -cf "$SUDOERS_FILE"

echo "Done. You can now run without password:"
echo "  sudo -n $INSPIRE_BIN"
