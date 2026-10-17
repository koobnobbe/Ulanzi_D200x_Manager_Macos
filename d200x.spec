# PyInstaller spec of D200X Manager: "D200X Manager.app" on macOS, "D200X Manager.exe" on Windows.
# Built by tools/build-mac.sh and tools/build-windows.ps1, which first put the defaults for a new config folder
# (config.yaml, docs, lang, library, plugins, icons, VERSION) in build/defaults and the icon in build/.
import ast
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(SPECPATH)
DEFAULTS = os.path.join(ROOT, 'build', 'defaults')
NAME = 'D200X Manager'


def plugin_imports():
    """What the plugins import. They are loaded from the config folder at run time, so PyInstaller can't see them."""
    found = set()
    for path in glob.glob(os.path.join(ROOT, 'plugins', '*', '*.py')):
        with open(path, encoding='utf-8') as fp:
            tree = ast.parse(fp.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                found.add(node.module)
    return sorted(found)


hidden = plugin_imports() + collect_submodules('aiohttp') + ['html.parser', 'plistlib', 'runpy']
hidden += ['pystray._darwin', 'system.mac', 'system.mac_icon'] if sys.platform == 'darwin' else ['pystray._win32', 'system.windows']

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'web'), 'web'), (DEFAULTS, 'defaults')],
    hiddenimports=hidden,
    excludes=['tkinter', 'test', 'unittest'],
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False,
              icon=os.path.join(ROOT, 'build', 'AppIcon.icns'))
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(coll, name=f'{NAME}.app', icon=os.path.join(ROOT, 'build', 'AppIcon.icns'),
                 bundle_identifier='com.koobnobbe.d200x-manager',
                 info_plist={'CFBundleName': NAME, 'CFBundleDisplayName': NAME,
                             'CFBundleShortVersionString': open(os.path.join(DEFAULTS, 'VERSION')).read().strip(),
                             'LSUIElement': True,             # menu bar only, no Dock icon
                             'NSHighResolutionCapable': True})
else:
    # one file: just start the exe
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=NAME, console=False,
              icon=os.path.join(ROOT, 'build', 'AppIcon.ico'))
