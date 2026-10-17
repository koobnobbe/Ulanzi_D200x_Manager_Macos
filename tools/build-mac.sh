#!/bin/zsh
# Build "D200X Manager.app" (everything in it: Python, the code, the defaults for a new config folder).
#   tools/build-mac.sh            build into dist/
#   tools/build-mac.sh --install  and put it in /Applications/D200X Manager/ (the config folder is the folder
#                                 of the app, so it gets its own folder; the running app is stopped first)
# Needs the project's .venv with requirements-build.txt installed.
set -euo pipefail
ROOT=${0:A:h:h}
NAME="D200X Manager"
cd "$ROOT"

.venv/bin/python -m pip install -q -r requirements-build.txt
.venv/bin/python tools/stage_defaults.py
.venv/bin/python -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller d200x.spec
echo "built: $ROOT/dist/$NAME.app"

if [[ "${1:-}" == "--install" ]]; then
  osascript -e "tell application id \"com.koobnobbe.d200x-manager\" to quit" 2>/dev/null || true
  pkill -f "$NAME.app/Contents/MacOS/$NAME" 2>/dev/null || true
  sleep 1
  mkdir -p "/Applications/$NAME"
  rm -rf "/Applications/$NAME/$NAME.app"
  cp -R "dist/$NAME.app" "/Applications/$NAME/"
  echo "installed: /Applications/$NAME/$NAME.app"
fi
