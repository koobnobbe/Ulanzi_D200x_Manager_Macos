#!/bin/zsh
# Build "D200X Manager.app": a menu bar app that runs the manager from this project folder.
#   tools/macos-app/build.sh            build into dist/
#   tools/macos-app/build.sh --install  and copy it to /Applications (the running app is stopped first)
# Needs the Xcode command line tools (swiftc) and the project's .venv.
set -euo pipefail
HERE=${0:A:h}
PROJECT=${HERE:h:h}
NAME="D200X Manager"
APP="$PROJECT/dist/$NAME.app"
VERSION=$(git -C "$PROJECT" describe --always --dirty 2>/dev/null || echo dev)

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -target arm64-apple-macos13 -o "$APP/Contents/MacOS/$NAME" "$HERE/main.swift"

# icon and menu texts
TMP=$(mktemp -d)
"$PROJECT/.venv/bin/python" "$HERE/make_icon.py" "$TMP/AppIcon.iconset"
iconutil -c icns -o "$APP/Contents/Resources/AppIcon.icns" "$TMP/AppIcon.iconset"
"$PROJECT/.venv/bin/python" - "$PROJECT" "$APP/Contents/Resources/menu.json" <<'PY'
import glob, json, os, sys, yaml
project, out = sys.argv[1:]
texts = {}
for path in glob.glob(os.path.join(project, 'lang', '*.yaml')):
    with open(path, encoding='utf-8') as fp:
        texts[os.path.splitext(os.path.basename(path))[0]] = (yaml.safe_load(fp) or {}).get('mac_app') or {}
with open(out, 'w', encoding='utf-8') as fp:
    json.dump(texts, fp, ensure_ascii=False)
PY
rm -rf "$TMP"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>com.koobnobbe.d200x-manager</string>
  <key>CFBundleExecutable</key><string>$NAME</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>D200XProjectDir</key><string>$PROJECT</string>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP"
echo "built: $APP"

if [[ "${1:-}" == "--install" ]]; then
  osascript -e "tell application id \"com.koobnobbe.d200x-manager\" to quit" 2>/dev/null || true
  sleep 1
  rm -rf "/Applications/$NAME.app"
  cp -R "$APP" /Applications/
  echo "installed: /Applications/$NAME.app"
fi
