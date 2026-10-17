"""Put what a new config folder starts with in build/defaults, for d200x.spec (used by both build scripts).

From the project: docs, lang, library (without hidden.json, which is your own), plugins (without caches), icons and
the starting config.yaml from defaults/. Profiles and backgrounds are yours, so none are included.
Also build/defaults/VERSION (git describe) and the app icon: build/AppIcon.icns on macOS, build/AppIcon.ico on Windows.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
TARGET = os.path.join(BUILD, 'defaults')
sys.path.insert(0, ROOT)


def main():
    shutil.rmtree(TARGET, ignore_errors=True)
    os.makedirs(TARGET)
    ignore = shutil.ignore_patterns('__pycache__', '.DS_Store', 'hidden.json', '*.pyc')
    for name in ('docs', 'lang', 'library', 'plugins', 'icons'):
        shutil.copytree(os.path.join(ROOT, name), os.path.join(TARGET, name), ignore=ignore)
    shutil.copy2(os.path.join(ROOT, 'defaults', 'config.yaml'), os.path.join(TARGET, 'config.yaml'))
    try:
        version = subprocess.run(['git', 'describe', '--always', '--dirty'], cwd=ROOT, capture_output=True,
                                 text=True, timeout=10).stdout.strip()
    except OSError:
        version = ''
    with open(os.path.join(TARGET, 'VERSION'), 'w', encoding='utf-8') as fp:
        fp.write((version or 'dev') + '\n')

    from app_logo import draw
    big = draw()
    if sys.platform == 'win32':
        big.save(os.path.join(BUILD, 'AppIcon.ico'), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    else:
        iconset = os.path.join(BUILD, 'AppIcon.iconset')
        shutil.rmtree(iconset, ignore_errors=True)
        os.makedirs(iconset)
        for size in (16, 32, 128, 256, 512):
            big.resize((size, size)).save(os.path.join(iconset, f'icon_{size}x{size}.png'))
            big.resize((size * 2, size * 2)).save(os.path.join(iconset, f'icon_{size}x{size}@2x.png'))
        subprocess.run(['iconutil', '-c', 'icns', '-o', os.path.join(BUILD, 'AppIcon.icns'), iconset], check=True)
    print(f'defaults in {TARGET} (version {version or "dev"})')


if __name__ == '__main__':
    main()
