"""Where everything is: the program, the config folder, and the work folder for the cache.

The config folder holds all that is yours: config.yaml, profiles/, library/, plugins/, lang/, docs/, icons/,
backgrounds/, .env and plugins.local.yaml. It is the folder of the app (macOS: the folder the .app is in) or the
.exe, unless "D200X Manager config.txt" next to the app names another one. Run from source (python main.py), the
program's folder is the project folder, so that is the config folder too, as before.

A config folder without these gets them from the program the first time (config.yaml as a starting point). When
the program is a new version, docs/, lang/ and its own plugins are brought up to date; config.yaml, profiles,
libraries, icons and settings are never overwritten.

The work folder (the cache: the rendered key images) is the user's cache folder for the app; from source it is
the project folder. The manager runs in it: strmdck reads and writes .cache and .build there.
"""
import os
import shutil
import sys

NAME = 'D200X Manager'
FROZEN = bool(getattr(sys, 'frozen', False))      # the built app or exe (PyInstaller)
SOURCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = getattr(sys, '_MEIPASS', SOURCE)            # web/ and, in the app, defaults/
DEFAULTS = os.path.join(BUNDLE, 'defaults') if FROZEN else SOURCE
POINTER_NAME = f'{NAME} config.txt'
VERSION_FILE = '.app-version'
SEED = ['config.yaml', 'docs', 'lang', 'library', 'plugins', 'profiles', 'icons', 'backgrounds']
UPDATED = ['docs', 'lang']        # replaced by a new version of the program (and its own plugins, see seed())


def app_location():
    """The folder the app or exe is in; from source, the project folder."""
    if not FROZEN:
        return SOURCE
    path = os.path.abspath(sys.executable)
    if sys.platform == 'darwin' and '.app/Contents/MacOS' in path:
        path = path[:path.index('.app/Contents/MacOS') + len('.app')]
    return os.path.dirname(path)


def pointer_file():
    return os.path.join(app_location(), POINTER_NAME)


def default_config_dir():
    return app_location()


def read_config_dir():
    """The config folder: the first line of the pointer file that is not empty or a comment, else the default."""
    try:
        with open(pointer_file(), encoding='utf-8') as fp:
            for line in fp:
                line = line.strip()
                if line and not line.startswith('#'):
                    return os.path.abspath(os.path.expandvars(os.path.expanduser(line)))
    except OSError:
        pass
    return default_config_dir()


def set_config_dir(path):
    """Use another config folder from the next start. An empty path (or the default) removes the pointer file."""
    path = os.path.abspath(os.path.expandvars(os.path.expanduser(path.strip()))) if path and path.strip() else ''
    if not path or os.path.normcase(path) == os.path.normcase(default_config_dir()):
        if os.path.exists(pointer_file()):
            os.remove(pointer_file())
        return default_config_dir()
    os.makedirs(path, exist_ok=True)
    with open(pointer_file(), 'w', encoding='utf-8', newline='\n') as fp:
        fp.write(f'# The config folder of {NAME}: config.yaml, profiles, library, plugins, lang, docs, icons.\n'
                 '# Remove this file to use the folder of the app.\n'
                 f'{path}\n')
    return path


def _user_dir(kind):
    if sys.platform == 'darwin':
        return os.path.expanduser({'cache': '~/Library/Caches', 'logs': '~/Library/Logs'}[kind])
    return os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')


CONFIG_DIR = read_config_dir()
WORK_DIR = os.path.join(_user_dir('cache'), NAME) if FROZEN else SOURCE
CACHE_DIR = os.path.join(WORK_DIR, '.cache')
LOG_FILE = (os.path.join(_user_dir('logs'), f'{NAME}.log') if sys.platform == 'darwin'
            else os.path.join(_user_dir('cache'), NAME, 'manager.log'))


def config(*parts):
    """A path in the config folder."""
    return os.path.join(CONFIG_DIR, *parts)


def program_version():
    try:
        with open(os.path.join(DEFAULTS, 'VERSION'), encoding='utf-8') as fp:
            return fp.read().strip()
    except OSError:
        return 'source'


def _copy_missing(source, target):
    """Copy what is in source but not in target (files and folders), leaving what is there alone."""
    if os.path.isdir(source):
        os.makedirs(target, exist_ok=True)
        for name in os.listdir(source):
            if name in ('__pycache__', '.DS_Store'):
                continue
            _copy_missing(os.path.join(source, name), os.path.join(target, name))
    elif not os.path.exists(target):
        shutil.copy2(source, target)


def seed():
    """Fill a new config folder, and bring the program's parts of it up to date after an update."""
    if os.path.normcase(CONFIG_DIR) == os.path.normcase(DEFAULTS):
        return      # from source with the project as config folder: nothing to copy
    os.makedirs(CONFIG_DIR, exist_ok=True)
    version = program_version()
    try:
        with open(config(VERSION_FILE), encoding='utf-8') as fp:
            installed = fp.read().strip()
    except OSError:
        installed = None
    for name in SEED:
        source = os.path.join(DEFAULTS, name)
        if name == 'profiles' and not FROZEN:
            continue    # from source, the project's profiles are personal
        if os.path.exists(source):
            if installed != version and name in UPDATED and os.path.isdir(source):
                shutil.copytree(source, config(name), dirs_exist_ok=True)
            _copy_missing(source, config(name))
        elif name in ('profiles', 'backgrounds', 'icons'):
            os.makedirs(config(name), exist_ok=True)
    if installed != version:
        # the program's own plugins: new code replaces the old (their settings are in plugins.local.yaml)
        bundled = os.path.join(DEFAULTS, 'plugins')
        if os.path.isdir(bundled):
            for plugin in os.listdir(bundled):
                if os.path.isdir(os.path.join(bundled, plugin)):
                    shutil.copytree(os.path.join(bundled, plugin), config('plugins', plugin), dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns('__pycache__'))
        with open(config(VERSION_FILE), 'w', encoding='utf-8', newline='\n') as fp:
            fp.write(version + '\n')


def load_env():
    """TIMEZONE and the like from .env in the config folder (strmdck reads TIMEZONE when it is imported)."""
    try:
        with open(config('.env'), encoding='utf-8') as fp:
            for line in fp:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"\''))
    except OSError:
        pass


def prepare():
    """Before the manager starts: the config folder filled, .env read, and the work folder as current folder."""
    seed()
    load_env()
    os.makedirs(WORK_DIR, exist_ok=True)
    os.chdir(WORK_DIR)
