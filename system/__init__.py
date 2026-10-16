"""What differs between macOS and Windows: sending keys, the app in front, the clipboard, opening and showing apps.

`system.mac` and `system.windows` have the same functions; this module picks the one for this computer and adds
what both share: key combos ("cmd+c") and values per system in a shared config:

    app: {mac: /Applications/Mail.app, windows: 'C:\\Program Files\\...\\OUTLOOK.EXE'}
    keys: {mac: cmd+tab, windows: alt+tab}

A key whose app or keys only exist on the other system is "unavailable" here: it shows, but does nothing.
"""
import sys

from i18n import t

if sys.platform == 'darwin':
    from system import mac as _impl
    NAME, OTHER = 'mac', 'windows'
elif sys.platform == 'win32':
    from system import windows as _impl
    NAME, OTHER = 'windows', 'mac'
else:
    raise SystemExit('D200X Manager runs on macOS and Windows')

send_keys = _impl.send_keys
can_send_keys = _impl.can_send_keys
frontmost_app = _impl.frontmost_app
clipboard = _impl.clipboard
open_app = _impl.open_app
open_url = _impl.open_url
app_icon = _impl.app_icon
is_app = _impl.is_app
app_key = _impl.app_key
list_apps = _impl.list_apps
APP_DIR = _impl.APP_DIR
APP_FOLDERS = _impl.APP_FOLDERS
SETTINGS_HINT = _impl.SETTINGS_HINT

# Key names that exist on one system only. On the other, a key using them is unavailable instead of wrong.
ONLY_MAC = {'fn'}
ONLY_WINDOWS = {'win', 'windows', 'insert', 'printscreen'}
# Fields that may hold a value per system.
PER_SYSTEM = ('app', 'keys')


class Unavailable(ValueError):
    """A key, app or combo that exists on the other system only."""


def for_system(value):
    """The value for this system: a {mac: ..., windows: ...} gives its own part (None when it has none)."""
    if isinstance(value, dict) and (NAME in value or OTHER in value):
        return value.get(NAME)
    return value


def merge_for_system(old, new):
    """A value from the web interface (for this system only) into a field that may hold a value per system."""
    if isinstance(old, dict) and (NAME in old or OTHER in old):
        merged = {k: v for k, v in old.items() if k != NAME}
        if new not in (None, ''):
            merged[NAME] = new
        return merged or None
    return new


def parse_keys(keys):
    """Parse "cmd+c", "volumeup" (or a list of those) into [(kind, code, flags), ...] for send_keys.
    "cmd" is Ctrl on Windows, so cmd+c copies on both. Raises Unavailable for names of the other system."""
    combos = []
    for combo in [keys] if isinstance(keys, str) else keys:
        *mods, key = [part.strip().lower() for part in str(combo).split('+')]
        if key in _impl.MEDIA_KEYS and not mods:
            combos.append(('media', _impl.MEDIA_KEYS[key], 0))
            continue
        other = ONLY_WINDOWS if NAME == 'mac' else ONLY_MAC
        if key in other or any(m in other for m in mods):
            raise Unavailable(t('config.other_system', combo=combo))
        if key not in _impl.KEY_CODES or any(m not in _impl.MODIFIERS for m in mods):
            raise ValueError(t('config.unknown_combo', combo=combo))
        combos.append(('key', _impl.KEY_CODES[key], _impl.flags([_impl.MODIFIERS[m] for m in mods])))
    return combos
