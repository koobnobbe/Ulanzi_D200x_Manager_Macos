import concurrent.futures
import http.server
import json
import os
import threading
from urllib.parse import parse_qs, unquote, urlsplit

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'index.html')


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
            return {'page': self.call(manager.add_page)}
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
