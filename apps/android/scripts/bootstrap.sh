#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
SDK="$ROOT/.tools/android"
GRADLE="$ROOT/.tools/gradle"
mkdir -p "$SDK" "$GRADLE"
if [ ! -f "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
  curl -fL --retry 2 https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o "$SDK/command-tools.zip"
  unzip -q "$SDK/command-tools.zip" -d "$SDK/unpack"
  mkdir -p "$SDK/cmdline-tools"
  mv "$SDK/unpack/cmdline-tools" "$SDK/cmdline-tools/latest"
  rm -rf "$SDK/unpack" "$SDK/command-tools.zip"
fi
if [ ! -f "$GRADLE/gradle-8.10.2/bin/gradle" ]; then
  curl -fL --retry 2 https://downloads.gradle.org/distributions/gradle-8.10.2-bin.zip -o "$GRADLE/gradle.zip"
  unzip -q "$GRADLE/gradle.zip" -d "$GRADLE"
  rm "$GRADLE/gradle.zip"
fi
PROXY_ARGS=()
if [ -n "${HTTPS_PROXY:-}" ]; then
 read -r PROXY_HOST PROXY_PORT < <(node -e 'const u=new URL(process.env.HTTPS_PROXY);console.log(u.hostname,u.port||80)')
 PROXY_ARGS+=(--proxy=http "--proxy_host=$PROXY_HOST" "--proxy_port=$PROXY_PORT")
fi
set +o pipefail
yes | "$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" "${PROXY_ARGS[@]}" --licenses >/dev/null
set -o pipefail
"$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" "${PROXY_ARGS[@]}" 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0'
printf 'sdk.dir=%s\n' "$SDK" > "$ROOT/apps/android/android/local.properties"
