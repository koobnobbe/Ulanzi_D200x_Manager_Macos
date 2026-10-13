import concurrent.futures
import http.server
import io
import json
import os
import plistlib
import re
import threading
from urllib.parse import parse_qs, unquote, urlsplit

import yaml
from PIL import Image

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')


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


def list_library():
    folder = os.path.join(PROJECT_DIR, 'library')
    if not os.path.isdir(folder):
        return []
    sections = []
    for name in sorted(os.listdir(folder), key=str.lower):
        if not name.endswith('.yaml'):
            continue
        with open(os.path.join(folder, name)) as fp:
            entries = (yaml.safe_load(fp) or {}).get('buttons') or []
        sections.append({'section': os.path.splitext(name)[0],
                         'items': [{'title': e.get('title') or str(e.get('keys', '')), 'data': e} for e in entries]})
    return sections


def app_icon_png(app, size=32):
    with open(os.path.join(app, 'Contents', 'Info.plist'), 'rb') as fp:
        icon = plistlib.load(fp).get('CFBundleIconFile')
    if not icon:
        return None
    if not icon.endswith('.icns'):
        icon += '.icns'
    path = os.path.join(app, 'Contents', 'Resources', icon)
    if not os.path.exists(path):
        return None
    buf = io.BytesIO()
    Image.open(path).convert('RGBA').resize((size, size), Image.LANCZOS).save(buf, format='PNG')
    return buf.getvalue()


def library_path(section):
    if '/' in section or section.startswith('.'):
        raise ValueError('onbekende sectie')
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


def create_library(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,40}', name or ''):
        raise ValueError('ongeldige naam: gebruik letters, cijfers, spatie, - of _')
    path = library_path(name)
    if os.path.exists(path):
        raise ValueError(f'bibliotheek {name} bestaat al')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'x') as fp:
        fp.write(f'# Library section "{name}". Each entry is a key definition you can drag onto a key.\nbuttons: []\n')


def take_library_line(section, index):
    path = library_path(section)
    if not os.path.isfile(path):
        raise ValueError('onbekende sectie')
    with open(path) as fp:
        lines = fp.read().split('\n')
    entries = [i for i, line in enumerate(lines) if line.startswith('  - ')]
    if not 0 <= index < len(entries):
        raise ValueError('onbekend item')
    line = lines.pop(entries[index])
    with open(path, 'w') as fp:
        fp.write('\n'.join(lines))
    return line


def delete_library_entry(section, index):
    take_library_line(section, index)


def move_library_entry(section, index, target):
    if target == section:
        return
    if not os.path.isfile(library_path(target)):
        raise ValueError('onbekende sectie')
    line = take_library_line(section, index)
    append_library_line(library_path(target), line)


def list_icons():
    folder = os.path.join(PROJECT_DIR, 'icons')
    if not os.path.isdir(folder):
        return []
    return sorted(f'icons/{name}' for name in os.listdir(folder) if name.lower().endswith('.png'))


def make_icon(source, name=None):
    if not os.path.isfile(source) or not source.lower().endswith(IMAGE_EXTS):
        raise ValueError('geen afbeelding: kies een png, jpg, ico of icns')
    stem = re.sub(r'[^A-Za-z0-9_-]+', '_', name or os.path.splitext(os.path.basename(source))[0]).strip('_')
    if not stem:
        raise ValueError('geef een naam voor het icoon')
    os.makedirs(os.path.join(PROJECT_DIR, 'icons'), exist_ok=True)
    image = Image.open(source).convert('RGBA')
    image.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    canvas = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    canvas.paste(image, ((ICON_SIZE - image.width) // 2, (ICON_SIZE - image.height) // 2), image)
    canvas.save(os.path.join(PROJECT_DIR, 'icons', f'{stem}.png'))
    return f'icons/{stem}.png'


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
        if path == '/api/icon':
            return {'icon': make_icon(body['source'], body.get('name'))}
        if path == '/api/library/new':
            create_library(body.get('name', ''))
            return {}
        if path == '/api/key/clear':
            return {'error': self.call(manager.clear_key, body['name'], int(body['page']), int(body['number']))}
        if path == '/api/library/move':
            move_library_entry(body['section'], int(body['index']), body['target'])
            return {}
        if path == '/api/library/delete':
            delete_library_entry(body['section'], int(body['index']))
            return {}
        if path == '/api/library/add':
            key = self.call(manager.key_data, body['name'], int(body['page']), int(body['number']))
            if not key:
                raise ValueError('deze toets is leeg')
            add_library_entry(key)
            return {}
        if path == '/api/knobcfg':
            return {'error': self.call(manager.set_knob, body['profile'], body['name'], body['data'])}
        if path == '/api/key':
            return {'error': self.call(manager.set_key, body['name'], int(body['page']), int(body['number']), body['data'])}
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
