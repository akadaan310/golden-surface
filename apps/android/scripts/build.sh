#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
export ANDROID_HOME="$ROOT/.tools/android"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$ROOT/.tools/gradle/cache"
GRADLE="$ROOT/.tools/gradle/gradle-8.10.2/bin/gradle"
if [ ! -x "$GRADLE" ] || [ ! -d "$ANDROID_HOME/platforms/android-35" ]; then bash "$ROOT/apps/android/scripts/bootstrap.sh"; fi
PROXY_ARGS=()
if [ -n "${HTTPS_PROXY:-}" ]; then
 read -r PROXY_HOST PROXY_PORT < <(node -e 'const u=new URL(process.env.HTTPS_PROXY);console.log(u.hostname,u.port||80)')
 PROXY_ARGS+=("-Dhttps.proxyHost=$PROXY_HOST" "-Dhttps.proxyPort=$PROXY_PORT" "-Dhttp.proxyHost=$PROXY_HOST" "-Dhttp.proxyPort=$PROXY_PORT" "-Dhttp.nonProxyHosts=localhost|127.*")
fi
cd "$ROOT/apps/android/android"
"$GRADLE" "${PROXY_ARGS[@]}" --no-daemon :app:testDebugUnitTest :app:assembleDebug
mkdir -p "$ROOT/artifacts"
cp app/build/outputs/apk/debug/app-debug.apk "$ROOT/artifacts/golden-motion-debug.apk"
