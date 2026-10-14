import base64
import concurrent.futures
import http.server
import io
import json
import os
import re
import threading
import zipfile
from urllib.parse import parse_qs, unquote, urlsplit

import yaml
from PIL import Image

import i18n
from appicon import app_icon
from i18n import t

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')
DOCS_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'docs.html')


IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.ico', '.icns')


def browse(directory):
    directory = os.path.abspath(os.path.expanduser(directory))
    dirs, files = [], []
    for e in os.scandir(directory):
        if e.name.startswith('.'):
            continue
        if e.is_dir():
            dirs.append({'name': e.name, 'path': e.path})
        elif e.name.lower().endswith(IMAGE_EXTS):
            files.append({'name': e.name, 'path': e.path})
    dirs.sort(key=lambda e: e['name'].lower())
    files.sort(key=lambda e: e['name'].lower())
    return {'dir': directory, 'parent': os.path.dirname(directory), 'dirs': dirs, 'files': files}


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_SIZE = 192
BACKGROUND_MAX = 1960  # wide enough for 5 keys of 196px


HIDDEN_LIBRARIES = os.path.join(PROJECT_DIR, 'library', 'hidden.json')


def hidden_libraries():
    try:
        with open(HIDDEN_LIBRARIES) as fp:
            return set(json.load(fp).get('hidden') or [])
    except FileNotFoundError:
        return set()


def set_library_enabled(section, enabled):
    if not os.path.isfile(library_path(section)):
        raise ValueError(t('errors.unknown_section'))
    hidden = hidden_libraries()
    if enabled:
        hidden.discard(section)
    else:
        hidden.add(section)
    with open(HIDDEN_LIBRARIES, 'w') as fp:
        json.dump({'hidden': sorted(hidden)}, fp, indent=2)


def list_library():
    folder = os.path.join(PROJECT_DIR, 'library')
    if not os.path.isdir(folder):
        return []
    hidden = hidden_libraries()
    sections = []
    for name in sorted(os.listdir(folder), key=str.lower):
        if not name.endswith('.yaml'):
            continue
        with open(os.path.join(folder, name)) as fp:
            entries = (yaml.safe_load(fp) or {}).get('buttons') or []
        sections.append({'section': os.path.splitext(name)[0], 'enabled': os.path.splitext(name)[0] not in hidden,
                         'items': [{'title': e.get('title') or str(e.get('keys', '')), 'data': e} for e in entries]})
    return sections


def app_icon_png(app, size=64):
    """The app's icon as PNG bytes for the web interface (64 px, sharp on a Retina screen at 32 px)."""
    icon = app_icon(app)
    if icon is None:
        return None
    buf = io.BytesIO()
    icon.resize((size, size), Image.LANCZOS).save(buf, format='PNG')
    return buf.getvalue()


def library_path(section):
    if '/' in section or section.startswith('.'):
        raise ValueError(t('errors.unknown_section'))
    return os.path.join(PROJECT_DIR, 'library', f'{section}.yaml')


def append_library_line(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = open(path).read() if os.path.exists(path) else ''
    lines = text.rstrip('\n').split('\n') if text.strip() else []
    if 'buttons: []' in lines:
        lines[lines.index('buttons: []')] = 'buttons:'
    elif 'buttons:' not in lines:
        lines.append('buttons:')
    lines.append(line)
    with open(path, 'w') as fp:
        fp.write('\n'.join(lines) + '\n')


def add_library_entry(data):
    entry = yaml.safe_dump(data, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
    append_library_line(library_path('template'), f'  - {entry}')
    sync_library_zip('template')


# Icon files a library uses travel with it in library/<section>.zip, next to library/<section>.yaml.
# App icons are not files and are not in the zip.

def library_zip_path(section):
    return os.path.splitext(library_path(section))[0] + '.zip'


def library_entries(section):
    with open(library_path(section)) as fp:
        return (yaml.safe_load(fp) or {}).get('buttons') or []


def icon_file(entry):
    """The file name in icons/ of an entry's own icon ("icons/x.png" -> "x.png"), or None."""
    icon = entry.get('icon') if isinstance(entry, dict) else None
    name = os.path.basename(icon) if isinstance(icon, str) else ''
    return name if icon == f'icons/{name}' and name.lower().endswith('.png') else None


def zip_icon(section, name):
    path = library_zip_path(section)
    if not os.path.isfile(path):
        return None
    with zipfile.ZipFile(path) as archive:
        return archive.read(name) if name in archive.namelist() else None


def sync_library_zip(section):
    """Make the section's zip hold exactly the icon files its keys use, taken from the zip or from icons/."""
    files = {}
    for name in sorted({icon_file(e) for e in library_entries(section)} - {None}):
        data = zip_icon(section, name)
        if data is None and os.path.isfile(os.path.join(PROJECT_DIR, 'icons', name)):
            with open(os.path.join(PROJECT_DIR, 'icons', name), 'rb') as fp:
                data = fp.read()
        if data is not None:
            files[name] = data
    path = library_zip_path(section)
    if not files:
        if os.path.exists(path):
            os.remove(path)
        return
    with zipfile.ZipFile(path + '.tmp', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    os.replace(path + '.tmp', path)


def extract_library_icon(section, index):
    """Copy the icon of a library entry from its zip into icons/, unless icons/ already has that file."""
    entries = library_entries(section)
    if not 0 <= index < len(entries):
        raise ValueError(t('errors.unknown_item'))
    name = icon_file(entries[index])
    target = os.path.join(PROJECT_DIR, 'icons', name) if name else None
    if not name or os.path.exists(target):
        return
    data = zip_icon(section, name)
    if data is not None:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as fp:
            fp.write(data)


def library_icon(section, name):
    """PNG bytes of a library entry's icon for the library panel: from icons/, else from the section's zip."""
    if os.path.basename(name) != name or not name.lower().endswith('.png'):
        return None
    path = os.path.join(PROJECT_DIR, 'icons', name)
    if os.path.isfile(path):
        with open(path, 'rb') as fp:
            return fp.read()
    return zip_icon(section, name)


def read_icon_zip(data):
    """{name: png bytes} from an uploaded icon zip; raises ValueError if it is not a zip of png images."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        files = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = os.path.basename(info.filename)
            if name.startswith('.') or '__MACOSX' in info.filename:
                continue  # Finder adds these when it makes a zip
            if not name.lower().endswith('.png'):
                raise ValueError(name)
            content = archive.read(info)
            Image.open(io.BytesIO(content)).verify()
            files[name] = content
        return files
    except Exception:
        raise ValueError(t('errors.bad_zip'))


def create_library(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,40}', name or ''):
        raise ValueError(t('errors.invalid_name'))
    path = library_path(name)
    if os.path.exists(path):
        raise ValueError(t('errors.library_exists', name=name))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'x') as fp:
        fp.write(f'# Library section "{name}". Each entry is a key definition you can drag onto a key.\nbuttons: []\n')


def import_library(filename, text, check, zip_data=None):
    """Copy a library file (and its icon zip) into library/ after `check` (which raises on a bad file) accepts it."""
    name = os.path.splitext(os.path.basename(filename or ''))[0]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,40}', name):
        raise ValueError(t('errors.invalid_filename'))
    if not (filename or '').lower().endswith(('.yaml', '.yml')):
        raise ValueError(t('errors.choose_yaml'))
    path = library_path(name)
    if os.path.exists(path):
        raise ValueError(t('errors.library_exists', name=name))
    icons = read_icon_zip(zip_data) if zip_data else {}
    entries = check(text, icons)
    # Moving and deleting entries works line by line, so every key must sit on one "  - {...}" line.
    lines = [line for line in text.split('\n') if line.startswith('  - ')]
    one_per_line = len(lines) == len(entries) and all(yaml.safe_load(line[4:]) == e for line, e in zip(lines, entries))
    if not one_per_line:
        flows = [yaml.safe_dump(e, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
                 for e in entries]
        text = f'# Library section "{name}" (imported).\nbuttons:' + ''.join(f'\n  - {f}' for f in flows) + ('\n' if flows else ' []\n')
    with open(path, 'x') as fp:
        fp.write(text)
    if icons:
        with zipfile.ZipFile(library_zip_path(name), 'w', zipfile.ZIP_DEFLATED) as archive:
            for icon, data in icons.items():
                archive.writestr(icon, data)
        sync_library_zip(name)  # keep only the icons the keys use
    return name


def take_library_line(section, index):
    path = library_path(section)
    if not os.path.isfile(path):
        raise ValueError(t('errors.unknown_section'))
    with open(path) as fp:
        lines = fp.read().split('\n')
    entries = [i for i, line in enumerate(lines) if line.startswith('  - ')]
    if not 0 <= index < len(entries):
        raise ValueError(t('errors.unknown_item'))
    line = lines.pop(entries[index])
    with open(path, 'w') as fp:
        fp.write('\n'.join(lines))
    return line


def delete_library_entry(section, index):
    take_library_line(section, index)
    sync_library_zip(section)


def move_library_entry(section, index, target):
    if target == section:
        return
    if not os.path.isfile(library_path(target)):
        raise ValueError(t('errors.unknown_section'))
    name = icon_file(library_entries(section)[index]) if 0 <= index < len(library_entries(section)) else None
    data = zip_icon(section, name) if name else None
    line = take_library_line(section, index)
    append_library_line(library_path(target), line)
    if data is not None and zip_icon(target, name) is None:
        # Bring the icon along before the source zip forgets it.
        with zipfile.ZipFile(library_zip_path(target), 'a', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(name, data)
    sync_library_zip(target)
    sync_library_zip(section)


def list_icons():
    folder = os.path.join(PROJECT_DIR, 'icons')
    if not os.path.isdir(folder):
        return []
    return sorted(f'icons/{name}' for name in os.listdir(folder) if name.lower().endswith('.png'))


def make_icon(source, name=None):
    if not os.path.isfile(source) or not source.lower().endswith(IMAGE_EXTS):
        raise ValueError(t('errors.not_an_image'))
    stem = re.sub(r'[^A-Za-z0-9_-]+', '_', name or os.path.splitext(os.path.basename(source))[0]).strip('_')
    if not stem:
        raise ValueError(t('errors.icon_name_needed'))
    os.makedirs(os.path.join(PROJECT_DIR, 'icons'), exist_ok=True)
    image = Image.open(source).convert('RGBA')
    image.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    canvas = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    canvas.paste(image, ((ICON_SIZE - image.width) // 2, (ICON_SIZE - image.height) // 2), image)
    canvas.save(os.path.join(PROJECT_DIR, 'icons', f'{stem}.png'))
    return f'icons/{stem}.png'


def list_backgrounds():
    folder = os.path.join(PROJECT_DIR, 'backgrounds')
    if not os.path.isdir(folder):
        return []
    return sorted(f'backgrounds/{name}' for name in os.listdir(folder) if name.lower().endswith('.png'))


def make_background(source, name=None):
    if not os.path.isfile(source) or not source.lower().endswith(IMAGE_EXTS):
        raise ValueError(t('errors.not_an_image'))
    stem = re.sub(r'[^A-Za-z0-9_-]+', '_', name or os.path.splitext(os.path.basename(source))[0]).strip('_')
    if not stem:
        raise ValueError(t('errors.image_name_needed'))
    os.makedirs(os.path.join(PROJECT_DIR, 'backgrounds'), exist_ok=True)
    image = Image.open(source).convert('RGB')
    image.thumbnail((BACKGROUND_MAX, BACKGROUND_MAX), Image.LANCZOS)
    image.save(os.path.join(PROJECT_DIR, 'backgrounds', f'{stem}.png'))
    return f'backgrounds/{stem}.png'


def list_apps(directory):
    directory = os.path.expanduser(directory)
    entries = [e for e in os.scandir(directory) if e.name.endswith('.app') and e.is_dir()]
    entries.sort(key=lambda e: e.name.lower())
    return {'dir': directory, 'apps': [{'name': e.name[:-4], 'path': e.path} for e in entries]}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def call(self, fn, *args):
        """Run fn on the asyncio loop thread, where the deck and config are handled."""
        future = concurrent.futures.Future()

        def run():
            try:
                future.set_result(fn(*args))
            except Exception as e:
                future.set_exception(e)

        self.server.loop.call_soon_threadsafe(run)
        return future.result(timeout=15)

    def send(self, status, body, content_type):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send(status, json.dumps(obj), 'application/json')

    def do_GET(self):
        path = urlsplit(self.path).path
        manager = self.server.manager
        if path == '/':
            with open(PAGE, 'rb') as fp:
                self.send(200, fp.read(), 'text/html; charset=utf-8')
        elif path in ('/docs', '/docs/'):
            with open(DOCS_PAGE, 'rb') as fp:
                self.send(200, fp.read(), 'text/html; charset=utf-8')
        elif path.startswith('/docs/'):
            # Wiki pages are the Markdown files in docs/; images next to them are served too.
            name = unquote(path[len('/docs/'):])
            file = os.path.join(PROJECT_DIR, 'docs', name)
            types = {'.md': 'text/markdown; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg'}
            kind = types.get(os.path.splitext(name)[1].lower())
            if os.path.basename(name) != name or not kind or not os.path.isfile(file):
                self.send_json({'error': 'not found'}, 404)
                return
            with open(file, 'rb') as fp:
                self.send(200, fp.read(), kind)
        elif path == '/api/ui':
            self.send_json(self.call(manager.ui_settings))
        elif path == '/api/lang':
            self.send_json(i18n.texts())
        elif path == '/library/icon':
            query = parse_qs(urlsplit(self.path).query)
            try:
                data = library_icon(query['section'][0], query['name'][0])
            except Exception:
                data = None
            if data is None:
                self.send_json({'error': 'not found'}, 404)
            else:
                self.send(200, data, 'image/png')
        elif path == '/api/library':
            try:
                self.send_json({'sections': list_library()})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/icons':
            self.send_json({'icons': list_icons()})
        elif path == '/api/browse':
            directory = parse_qs(urlsplit(self.path).query).get('dir', ['~'])[0]
            try:
                self.send_json(browse(directory))
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/device':
            self.send_json(self.call(manager.device_settings))
        elif path == '/api/backgrounds':
            self.send_json({'backgrounds': list_backgrounds()})
        elif path.startswith('/backgrounds/'):
            name = unquote(path[len('/backgrounds/'):])
            file = os.path.join(PROJECT_DIR, 'backgrounds', name)
            if os.path.basename(name) != name or not name.endswith('.png') or not os.path.isfile(file):
                self.send_json({'error': 'not found'}, 404)
                return
            with open(file, 'rb') as fp:
                self.send(200, fp.read(), 'image/png')
        elif path == '/api/apps':
            directory = parse_qs(urlsplit(self.path).query).get('dir', ['/Applications'])[0]
            try:
                self.send_json(list_apps(directory))
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/knobdata':
            query = parse_qs(urlsplit(self.path).query)
            try:
                knob = self.call(manager.knob_data, query['profile'][0], query['name'][0])
                self.send_json({'knob': knob})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/preview':
            query = parse_qs(urlsplit(self.path).query)
            try:
                self.send_json(self.call(manager.preview, query['name'][0], int(query['page'][0])))
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/key':
            query = parse_qs(urlsplit(self.path).query)
            try:
                key = self.call(manager.key_data, query['name'][0], int(query['page'][0]), int(query['number'][0]))
                self.send_json({'key': key})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/file':
            name = parse_qs(urlsplit(self.path).query).get('name', ['default'])[0]
            try:
                self.send_json({'text': self.call(manager.read_file, name)})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif path == '/api/state':
            with open(manager.active_path()) as fp:
                text = fp.read()
            self.send_json({'text': text, **self.call(manager.state)})
        elif path == '/appicon':
            app = parse_qs(urlsplit(self.path).query).get('path', [''])[0]
            data = app_icon_png(app) if app.endswith('.app') and os.path.isdir(app) else None
            if data is None:
                self.send_json({'error': 'no icon'}, 404)
            else:
                self.send(200, data, 'image/png')
        elif path.startswith('/web/'):
            name = unquote(path[len('/web/'):])
            file = os.path.join(os.path.dirname(PAGE), name)
            if os.path.basename(name) != name or not name.endswith('.png') or not os.path.isfile(file):
                self.send_json({'error': 'not found'}, 404)
                return
            with open(file, 'rb') as fp:
                self.send(200, fp.read(), 'image/png')
        elif path.startswith('/icons/'):
            name = unquote(path[len('/icons/'):])
            file = os.path.join(PROJECT_DIR, 'icons', name)
            if os.path.basename(name) != name or not name.endswith('.png') or not os.path.isfile(file):
                self.send_json({'error': 'not found'}, 404)
                return
            with open(file, 'rb') as fp:
                self.send(200, fp.read(), 'image/png')
        elif path.startswith('/icon/'):
            name = unquote(path[len('/icon/'):])
            file = os.path.join(self.server.icon_dir, name)
            if os.path.basename(name) != name or not name.endswith('.png') or not os.path.isfile(file):
                self.send_json({'error': 'not found'}, 404)
                return
            with open(file, 'rb') as fp:
                self.send(200, fp.read(), 'image/png')
        else:
            self.send_json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlsplit(self.path).path
        length = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
            result = self.route(path, body)
        except Exception as e:
            self.send_json({'error': str(e)}, 400)
            return
        if result is None:
            self.send_json({'error': 'not found'}, 404)
        else:
            self.send_json(result)

    def route(self, path, body):
        manager = self.server.manager
        if path == '/api/save':
            return {'error': self.call(manager.save_file, body.get('name', 'default'), body['text'])}
        if path == '/api/device':
            return {'error': self.call(manager.set_device, body)}
        if path == '/api/ui':
            return {'error': self.call(manager.set_ui, body)}
        if path == '/api/background':
            return {'background': make_background(body['source'], body.get('name'))}
        if path == '/api/icon':
            return {'icon': make_icon(body['source'], body.get('name'))}
        if path == '/api/library/new':
            create_library(body.get('name', ''))
            return {}
        if path == '/api/key/clear':
            return {'error': self.call(manager.clear_key, body['name'], int(body['page']), int(body['number']))}
        if path == '/api/library/import':
            zip_data = base64.b64decode(body['zip']) if body.get('zip') else None
            return {'section': import_library(body.get('filename'), body.get('text', ''), manager.check_library, zip_data)}
        if path == '/api/library/extract':
            extract_library_icon(body['section'], int(body['index']))
            return {}
        if path == '/api/library/enabled':
            set_library_enabled(body['section'], bool(body['enabled']))
            return {}
        if path == '/api/library/move':
            move_library_entry(body['section'], int(body['index']), body['target'])
            return {}
        if path == '/api/library/delete':
            delete_library_entry(body['section'], int(body['index']))
            return {}
        if path == '/api/library/add':
            key = self.call(manager.key_data, body['name'], int(body['page']), int(body['number']))
            if not key:
                raise ValueError(t('errors.key_empty'))
            add_library_entry(key)
            return {}
        if path == '/api/knobcfg':
            return {'error': self.call(manager.set_knob, body['profile'], body['name'], body['data'])}
        if path == '/api/key':
            return {'error': self.call(manager.set_key, body['name'], int(body['page']), int(body['number']), body['data'])}
        if path == '/api/profile/settings':
            data = {k: body[k] for k in ('app', 'background_image', 'background_color') if k in body}
            return {'error': self.call(manager.set_profile_settings, body['name'], data)}
        if path == '/api/page/settings':
            return {'error': self.call(manager.set_page_settings, body['name'], int(body['page']), body.get('settings') or {})}
        if path == '/api/page/move':
            page, error = self.call(manager.move_page, body['name'], int(body['page']), 1 if int(body['direction']) > 0 else -1)
            return {'page': page, 'error': error}
        if path == '/api/page/delete':
            return {'error': self.call(manager.delete_page, body['name'], int(body['page']))}
        if path == '/api/profile/new':
            return {'name': self.call(manager.create_profile, body.get('name', ''))}
        if path == '/api/press':
            steps = self.call(manager.plan_button, int(body['number']))
        elif path == '/api/knob':
            steps = self.call(manager.plan_knob, int(body['index']), body['event'])
        elif path == '/api/brightness':
            self.call(manager.set_brightness, int(body['value']))
            return {}
        elif path == '/api/pages/add':
            return {'page': self.call(manager.add_page, body.get('name'))}
        elif path == '/api/page':
            self.call(lambda: manager.goto(manager.page_number(str(body['page']))))
            return {}
        elif path == '/api/reload':
            self.call(manager.load)
            return {}
        else:
            return None
        if body.get('run'):
            self.call(manager.run, steps)
        return {'steps': [description for description, _ in steps]}


def start(manager, loop, icon_dir, port):
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    except OSError as e:
        print(f'web interface not started: {e}')
        return
    server.manager, server.loop, server.icon_dir = manager, loop, icon_dir
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'web interface: http://127.0.0.1:{port}')
