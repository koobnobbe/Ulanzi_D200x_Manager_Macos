"""Plugins: local code in plugins/<id>/ that adds key and knob types, live state and its own settings.

A plugin folder has a manifest, plugin.yaml, that declares its key types with their fields and its settings,
and a Python module with a Plugin subclass. The key types of every plugin are known from the manifests, also
when the plugin is turned off or fails to start, so a config that uses them always loads; such keys just show
that the plugin is off.

Settings are per machine, in plugins.local.yaml next to config.yaml (not in git): an "enabled" flag and the
values of the settings in the manifest, secrets included.
"""
import importlib.util
import inspect
import os
import re
import traceback

import yaml
from PIL import Image, ImageDraw

import i18n
from i18n import t

import paths

PROJECT_DIR = paths.CONFIG_DIR      # the config folder (the name is older than the config folder)
CACHE_DIR = paths.CACHE_DIR         # for plugins: files they keep, such as fetched icons
PLUGIN_DIR = paths.config('plugins')
LOCAL_SETTINGS = paths.config('plugins.local.yaml')
ENTITY_ID = re.compile(r'[a-z_]+\.[a-z0-9_]+')

host = None   # the running Host, set by Host(); render() and the checks below also work without one


class Plugin:
    """Base class for plugin code. Override what the plugin needs; every method is called on the event loop."""

    def __init__(self, ctx):
        self.ctx = ctx

    async def start(self):
        """Connect, subscribe, start background tasks. Called when the plugin is turned on or its settings change."""

    async def stop(self):
        """Undo start()."""

    def status(self):
        """{'state': 'connected' | 'connecting' | 'error' | ..., 'message': text for the Plugins dialog}."""
        return {'state': 'running', 'message': ''}

    def validate(self, kind, entry):
        """A problem with a key or knob of one of this plugin's types (text), or None. Fields are already checked."""
        return None

    def actions(self, kind, entry, event):
        """What a key press ('press') or knob event ('left', 'right', 'press') does: [(description, function)].
        A function may return an awaitable; it then runs as a task."""
        return []

    def render(self, kind, entry):
        """The face of a key as an RGBA image of ctx.size x ctx.size, drawn on top of the key's background; or None."""
        return None

    def watches(self, kind, entry):
        """Ids of things this key shows; when one changes, call ctx.refresh({id}) to redraw the key."""
        return set()

    async def call(self, action, data):
        """Requests from the web interface, e.g. a list of entities for a picker or a connection test."""
        raise ValueError(f'unknown action {action}')


class Context:
    """What a plugin gets from the manager."""

    def __init__(self, plugin_id, settings, refresh, size, font):
        self.id = plugin_id
        self.settings = settings
        self.size = size              # key size in pixels
        self.font = font              # font(size) -> the font the deck uses
        self._refresh = refresh

    def refresh(self, ids=None):
        """Redraw the keys that watch any of these ids (all of this plugin's keys when ids is None)."""
        self._refresh(self.id, ids)

    def t(self, key, **values):
        return t(f'plugin.{self.id}.{key}', **values)


def read_local():
    try:
        with open(LOCAL_SETTINGS, encoding='utf-8') as fp:
            return yaml.safe_load(fp) or {}
    except FileNotFoundError:
        return {}


def write_local(data):
    text = ('# Plugin settings for this machine: which plugins are on, and their settings and secrets.\n'
            '# Not in git (see .gitignore); every machine has its own.\n')
    text += yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    with open(LOCAL_SETTINGS + '.tmp', 'w', encoding='utf-8') as fp:
        fp.write(text)
    os.chmod(LOCAL_SETTINGS + '.tmp', 0o600)   # it holds tokens
    os.replace(LOCAL_SETTINGS + '.tmp', LOCAL_SETTINGS)


_manifest_cache = (None, {})


def manifests():
    """{plugin id: manifest} for every folder in plugins/ with a plugin.yaml. Cached until a manifest changes."""
    global _manifest_cache
    if not os.path.isdir(PLUGIN_DIR):
        return {}
    paths = [os.path.join(PLUGIN_DIR, name, 'plugin.yaml') for name in sorted(os.listdir(PLUGIN_DIR))]
    stamp = tuple((p, os.path.getmtime(p)) for p in paths if os.path.isfile(p))
    if stamp == _manifest_cache[0]:
        return _manifest_cache[1]
    found = {}
    for path, _ in stamp:
        name = os.path.basename(os.path.dirname(path))
        try:
            with open(path, encoding='utf-8') as fp:
                manifest = yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            continue
        manifest['id'] = name
        manifest['dir'] = os.path.join(PLUGIN_DIR, name)
        found[name] = manifest
    _manifest_cache = (stamp, found)
    return found


def key_types():
    """{type name: (plugin id, spec)} for every key and knob type of every plugin, on or off."""
    return {name: (pid, spec) for pid, manifest in manifests().items()
            for name, spec in (manifest.get('key_types') or {}).items()}


def field_names():
    """All field names that plugin key types use, for the library and config checks."""
    return {f['key'] for _, spec in key_types().values() for f in spec.get('fields') or []}


def check_fields(kind, entry):
    """Check an entry against the fields of its plugin type. Returns a problem text or None."""
    found = key_types().get(kind)
    if not found:
        return None
    pid, spec = found
    for field in spec.get('fields') or []:
        value = entry.get(field['key'])
        label = field['key']
        if value in (None, ''):
            if field.get('required'):
                return t('plugins_check.field_needed', type=kind, field=label)
            continue
        if field.get('type') == 'entity':
            if not isinstance(value, str) or not ENTITY_ID.fullmatch(value):
                return t('plugins_check.not_an_entity', field=label, value=value)
            domains = field.get('domains')
            if domains and value.split('.')[0] not in domains:
                return t('plugins_check.wrong_domain', value=value, domains=', '.join(domains))
        elif field.get('type') == 'number':
            if not isinstance(value, (int, float)) or not field.get('min', value) <= value <= field.get('max', value):
                return t('plugins_check.number_range', field=label, min=field.get('min', ''), max=field.get('max', ''))
        elif field.get('type') == 'choice':
            if value not in (field.get('options') or []):
                return t('plugins_check.not_an_option', field=label, value=value, options=', '.join(map(str, field.get('options') or [])))
    if host and pid in host.running:
        return host.running[pid].validate(kind, entry)
    return None


def is_plugin_type(kind):
    return kind in key_types()


def plugin_kind(kind):
    """'key' or 'knob' for a plugin type, None for others."""
    found = key_types().get(kind)
    return found[1].get('kind', 'key') if found else None


def render(kind, entry, size, font):
    """The face of a plugin key, or a placeholder when its plugin is off or draws nothing."""
    if host:
        image = host.render(kind, entry)
        if image is not None:
            return image
    found = key_types().get(kind)
    plugin_name = (manifests().get(found[0]) or {}).get('name', found[0]) if found else kind
    return placeholder(entry.get('title') or kind, plugin_name, size, font)


def placeholder(title, plugin_name, size, font):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((size / 2, size / 2 - 14), str(title), font=font(30), fill='#ffffff', anchor='mm')
    draw.text((size / 2, size / 2 + 22), t('plugins_check.off', name=plugin_name), font=font(20), fill='#8a8aa0', anchor='mm')
    return img


def actions(kind, entry, event):
    if host:
        return host.actions(kind, entry, event)
    return []


def watches(kind, entry):
    """What a key shows: the values of its entity fields, plus whatever its plugin adds."""
    found = key_types().get(kind)
    ids = {entry[f['key']] for f in (found[1].get('fields') or []) if f.get('type') == 'entity' and entry.get(f['key'])} if found else set()
    if host:
        ids |= host.watches(kind, entry)
    return ids


class Host:
    """Loads, starts and stops the plugins, and passes calls from the manager and the web interface on."""

    def __init__(self, refresh, size, font):
        global host
        host = self
        self._refresh = refresh
        self.size, self.font = size, font
        self.running = {}     # id -> Plugin instance, only plugins that started
        self.errors = {}      # id -> error text of a plugin that failed to load or start

    async def start_all(self):
        local = read_local()
        for pid in manifests():
            if (local.get(pid) or {}).get('enabled'):
                await self.start(pid)

    async def start(self, pid):
        await self.stop(pid)
        manifest = manifests().get(pid)
        if not manifest:
            return
        settings = {k: v for k, v in (read_local().get(pid) or {}).items() if k != 'enabled'}
        try:
            path = os.path.join(manifest['dir'], manifest.get('module', 'plugin.py'))
            spec = importlib.util.spec_from_file_location(f'd200x_plugin_{pid}', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls = getattr(module, manifest.get('class', 'Plugin'))
            plugin = cls(Context(pid, settings, self._refresh, self.size, self.font))
            await plugin.start()
        except Exception as e:
            traceback.print_exc()
            self.errors[pid] = f'{type(e).__name__}: {e}'
            print(f'plugin {pid} failed to start: {e}')
            return
        self.errors.pop(pid, None)
        self.running[pid] = plugin
        print(f'plugin {pid} started')
        self._refresh(pid, None)

    async def stop(self, pid):
        plugin = self.running.pop(pid, None)
        if plugin:
            try:
                await plugin.stop()
            except Exception as e:
                print(f'plugin {pid} failed to stop: {e}')
            self._refresh(pid, None)

    def _plugin_for(self, kind):
        found = key_types().get(kind)
        return self.running.get(found[0]) if found else None

    def render(self, kind, entry):
        plugin = self._plugin_for(kind)
        if not plugin:
            return None
        try:
            return plugin.render(kind, entry)
        except Exception as e:
            print(f'plugin render error ({kind}): {e}')
            return None

    def actions(self, kind, entry, event):
        plugin = self._plugin_for(kind)
        if not plugin:
            text = t('plugins_check.off', name=kind)
            return [(text, lambda: print(text))]
        try:
            return plugin.actions(kind, entry, event)
        except Exception as e:
            print(f'plugin action error ({kind}): {e}')
            return []

    def watches(self, kind, entry):
        plugin = self._plugin_for(kind)
        try:
            return set(plugin.watches(kind, entry)) if plugin else set()
        except Exception:
            return set()

    # --- for the web interface
    def describe(self):
        """Every plugin with its state and settings; secrets are never sent, only whether they are set."""
        local = read_local()
        result = []
        for pid, manifest in manifests().items():
            values = local.get(pid) or {}
            settings = []
            for field in manifest.get('settings') or []:
                item = {**field, 'label': t(f"plugin.{pid}.{field.get('label', 'settings.' + field['key'])}")}
                if field.get('type') == 'secret':
                    item['is_set'] = bool(values.get(field['key']))
                else:
                    item['value'] = values.get(field['key'], field.get('default'))
                settings.append(item)
            plugin = self.running.get(pid)
            if pid in self.errors:
                status = {'state': 'error', 'message': self.errors[pid]}
            elif not values.get('enabled'):
                status = {'state': 'off', 'message': ''}
            elif plugin:
                status = plugin.status()
            else:
                status = {'state': 'starting', 'message': ''}
            def field_info(f):
                info = {**f, 'label': t(f"plugin.{pid}.{f.get('label', 'fields.' + f['key'])}")}
                if f.get('type') == 'choice':
                    info['options'] = [{'value': o, 'label': t(f"plugin.{pid}.options.{f['key']}.{o}")} for o in f.get('options') or []]
                return info
            types = [{'type': name, 'kind': spec.get('kind', 'key'),
                      'label': t(f"plugin.{pid}.{spec.get('label', 'types.' + name)}"),
                      'fields': [field_info(f) for f in spec.get('fields') or []]}
                     for name, spec in (manifest.get('key_types') or {}).items()]
            result.append({'id': pid, 'name': manifest.get('name', pid), 'version': manifest.get('version', ''),
                           'description': t(f'plugin.{pid}.description'), 'enabled': bool(values.get('enabled')),
                           'status': status, 'settings': settings, 'key_types': types})
        return result

    def merged_settings(self, pid, settings):
        """The stored settings of a plugin with new values on top; an empty secret keeps the stored one."""
        manifest = manifests().get(pid)
        if not manifest:
            raise ValueError(t('plugins_check.unknown_plugin', id=pid))
        current = read_local().get(pid) or {}
        merged = dict(current)
        for field in manifest.get('settings') or []:
            key = field['key']
            if key not in settings:
                continue
            value = settings[key]
            if field.get('type') == 'secret' and not value:
                continue
            if field.get('type') == 'bool':
                value = bool(value)
            elif field.get('type') == 'number':
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise ValueError(t('plugins_check.number_range', field=key, min=field.get('min', ''), max=field.get('max', '')))
                if not field.get('min', value) <= value <= field.get('max', value):
                    raise ValueError(t('plugins_check.number_range', field=key, min=field.get('min', ''), max=field.get('max', '')))
                value = int(value) if value == int(value) else value
            merged[key] = value
        return merged

    async def save_settings(self, pid, settings):
        local = read_local()
        local[pid] = self.merged_settings(pid, settings)
        write_local(local)
        if local[pid].get('enabled'):
            await self.start(pid)

    async def set_enabled(self, pid, enabled):
        if pid not in manifests():
            raise ValueError(t('plugins_check.unknown_plugin', id=pid))
        local = read_local()
        local.setdefault(pid, {})['enabled'] = bool(enabled)
        write_local(local)
        if enabled:
            await self.start(pid)
        else:
            await self.stop(pid)

    async def call(self, pid, action, data):
        """A request from the web interface. 'test' also works when the plugin is off: it gets a temporary instance."""
        plugin = self.running.get(pid)
        if action == 'test':
            manifest = manifests().get(pid)
            path = os.path.join(manifest['dir'], manifest.get('module', 'plugin.py'))
            spec = importlib.util.spec_from_file_location(f'd200x_plugin_{pid}_test', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            settings = {k: v for k, v in self.merged_settings(pid, data or {}).items() if k != 'enabled'}
            temporary = getattr(module, manifest.get('class', 'Plugin'))(Context(pid, settings, lambda *a: None, self.size, self.font))
            return await temporary.call('test', settings)
        if not plugin:
            raise ValueError(t('plugins_check.not_running', name=(manifests().get(pid) or {}).get('name', pid)))
        result = plugin.call(action, data or {})
        return await result if inspect.isawaitable(result) else result
