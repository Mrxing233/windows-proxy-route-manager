#!/usr/bin/env bash
set -u

APP_NAME="macOS app"
PROXY_HOST="127.0.0.1"
PROXY_PORT="7897"
TEST_URL="https://example.com/"
SET_SHELL_ENV=0
SET_LAUNCHCTL_ENV=0
PRINT_ENV=0

usage() {
  cat <<'EOF'
Usage:
  diagnose-macos-app-proxy.sh [options]

Options:
  --proxy-host <host>        Local or enterprise proxy host. Default: 127.0.0.1
  --proxy-port <port>        Local or enterprise proxy port. Default: 7897
  --app-name <name>          Process/app name to search for. Default: macOS app
  --test-url <url>           URL used for direct/proxy connectivity checks. Default: https://example.com/
  --print-env                Print suggested proxy environment variables.
  --set-shell-env            Append proxy exports to ~/.zshrc or ~/.bash_profile.
  --set-launchctl-env        Set launchctl user environment variables for newly launched GUI apps.
  -h, --help                 Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --proxy-host) PROXY_HOST="${2:-}"; shift 2 ;;
    --proxy-port) PROXY_PORT="${2:-}"; shift 2 ;;
    --app-name) APP_NAME="${2:-}"; shift 2 ;;
    --test-url) TEST_URL="${2:-}"; shift 2 ;;
    --print-env) PRINT_ENV=1; shift ;;
    --set-shell-env) SET_SHELL_ENV=1; shift ;;
    --set-launchctl-env) SET_LAUNCHCTL_ENV=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

PROXY_URL="http://${PROXY_HOST}:${PROXY_PORT}"
NO_PROXY_VALUE="localhost,127.0.0.1,::1"

section() {
  printf '\n==== %s ====\n' "$1"
}

section "macOS App Proxy Diagnose"
echo "App: ${APP_NAME}"
echo "Proxy: ${PROXY_URL}"
echo "Test URL: ${TEST_URL}"

section "Matching Processes"
if command -v pgrep >/dev/null 2>&1; then
  pgrep -fl "$APP_NAME" || true
else
  ps aux | grep -i "$APP_NAME" | grep -v grep || true
fi

section "Current Shell Proxy Environment"
env | grep -Ei '^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY)=' || true

section "launchctl Proxy Environment"
if command -v launchctl >/dev/null 2>&1; then
  for key in HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY; do
    value="$(launchctl getenv "$key" 2>/dev/null || true)"
    [ -n "$value" ] && echo "$key=$value"
  done
else
  echo "launchctl not available."
fi

section "macOS System Proxy Settings"
if command -v scutil >/dev/null 2>&1; then
  scutil --proxy
else
  echo "scutil not available."
fi

section "Local Proxy Port"
if command -v nc >/dev/null 2>&1; then
  nc -vz "$PROXY_HOST" "$PROXY_PORT"
else
  echo "nc not available; skip port check."
fi

section "Direct URL Test"
echo "> curl -I --connect-timeout 15 --max-time 30 ${TEST_URL}"
curl -I --connect-timeout 15 --max-time 30 "$TEST_URL"

section "Proxy URL Test"
echo "> curl -I --proxy ${PROXY_URL} --connect-timeout 15 --max-time 30 ${TEST_URL}"
curl -I --proxy "$PROXY_URL" --connect-timeout 15 --max-time 30 "$TEST_URL"

if [ "$PRINT_ENV" -eq 1 ]; then
  section "Suggested Shell Exports"
  cat <<EOF
export HTTP_PROXY=${PROXY_URL}
export HTTPS_PROXY=${PROXY_URL}
export ALL_PROXY=${PROXY_URL}
export NO_PROXY=${NO_PROXY_VALUE}
EOF
fi

if [ "$SET_SHELL_ENV" -eq 1 ]; then
  section "Set Shell Profile Environment"
  shell_name="$(basename "${SHELL:-}")"
  if [ "$shell_name" = "zsh" ]; then
    profile="${HOME}/.zshrc"
  else
    profile="${HOME}/.bash_profile"
  fi
  marker="# windows-proxy-route-manager"
  if [ -f "$profile" ] && grep -q "$marker" "$profile"; then
    echo "Profile already contains ${marker}: ${profile}"
  else
    {
      echo ""
      echo "$marker"
      echo "export HTTP_PROXY=${PROXY_URL}"
      echo "export HTTPS_PROXY=${PROXY_URL}"
      echo "export ALL_PROXY=${PROXY_URL}"
      echo "export NO_PROXY=${NO_PROXY_VALUE}"
    } >> "$profile"
    echo "Updated ${profile}. Open a new terminal or source the profile."
  fi
fi

if [ "$SET_LAUNCHCTL_ENV" -eq 1 ]; then
  section "Set launchctl Environment"
  if command -v launchctl >/dev/null 2>&1; then
    launchctl setenv HTTP_PROXY "$PROXY_URL"
    launchctl setenv HTTPS_PROXY "$PROXY_URL"
    launchctl setenv ALL_PROXY "$PROXY_URL"
    launchctl setenv NO_PROXY "$NO_PROXY_VALUE"
    echo "launchctl environment updated. Quit and reopen affected GUI apps."
  else
    echo "launchctl not available."
  fi
fi

section "Interpretation"
echo "- If direct test fails but proxy test returns HTTP headers, configure the app to use the proxy."
echo "- Shell profile changes affect newly opened terminals."
echo "- launchctl environment changes affect newly launched GUI apps."
echo "- Fully quit and restart the affected app after changes."
