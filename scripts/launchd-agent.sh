#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.uniubi.wechat-assistant"
DOMAIN="gui/$(id -u)"
TEMPLATE="$ROOT/launchd/$LABEL.plist.template"
DESTINATION="$HOME/Library/LaunchAgents/$LABEL.plist"

usage() {
  cat <<'EOF'
Usage: scripts/launchd-agent.sh <install|uninstall|status>

  install    Render the LaunchAgent plist, validate it, then load it for the current macOS user.
  uninstall  Stop the loaded LaunchAgent if present and remove its rendered plist.
  status     Show the current LaunchAgent state without changing it.
EOF
}

require_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "launchd is only available on macOS." >&2
    exit 1
  fi
}

is_loaded() {
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
}

render_plist() {
  local escaped_root
  escaped_root="$(printf '%s' "$ROOT" | sed 's/[&|]/\\&/g')"
  mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/runtime/logs"
  sed "s|__PROJECT_ROOT__|$escaped_root|g" "$TEMPLATE" >"$DESTINATION"
  plutil -lint "$DESTINATION" >/dev/null
}

install() {
  if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "Missing .venv. Run scripts/bootstrap-local.sh first." >&2
    exit 1
  fi
  if [[ ! -f "$ROOT/.env" ]]; then
    echo "Missing .env. Configure it before installing the LaunchAgent." >&2
    exit 1
  fi
  if is_loaded; then
    echo "$LABEL is already loaded. Run '$0 uninstall' before reinstalling it." >&2
    exit 1
  fi
  render_plist
  launchctl bootstrap "$DOMAIN" "$DESTINATION"
  echo "Installed and loaded $LABEL. Check it with: $0 status"
}

uninstall() {
  if is_loaded; then
    launchctl bootout "$DOMAIN/$LABEL"
  fi
  rm -f "$DESTINATION"
  echo "Removed $LABEL. Runtime logs and credentials were preserved."
}

status() {
  if is_loaded; then
    launchctl print "$DOMAIN/$LABEL"
    return
  fi
  echo "$LABEL is not loaded."
}

require_macos
case "${1:-}" in
  install) install ;;
  uninstall) uninstall ;;
  status) status ;;
  *) usage; exit 2 ;;
esac
