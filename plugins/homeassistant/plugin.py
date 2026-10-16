"""Home Assistant for the D200X: toggle lights and switches, show live states, dim a light with a knob.

Talks to Home Assistant's WebSocket API (/api/websocket) with a long-lived access token: it logs in, reads all
states, and subscribes to state_changed events. A change redraws only the keys that show that entity.
When the connection drops it reconnects with a growing delay, and the keys show that Home Assistant is offline.
"""
import asyncio
import ssl

import aiohttp
from PIL import Image, ImageDraw

from plugins import Plugin

S = 4                               # draw at 4x and scale down for smooth edges
LIGHT_ON = (255, 196, 64)           # a light that is on, when Home Assistant gives no color
SWITCH_ON = (52, 199, 89)
OFF = (120, 120, 132)
WARN = (255, 105, 97)


class HomeAssistant(Plugin):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.states = {}            # entity_id -> state object from Home Assistant
        self.state, self.message = 'connecting', ''
        self.session = self.ws = self.task = None
        self.next_id = 1
        self.pending = {}           # message id -> future of the answer
        self.version = ''

    # --- connection
    def _ws_url(self, settings):
        url = str(settings.get('url') or '').strip().rstrip('/')
        if not url:
            raise ValueError(self.ctx.t('errors.no_url'))
        for http, ws in (('https://', 'wss://'), ('http://', 'ws://')):
            if url.startswith(http):
                return ws + url[len(http):] + '/api/websocket'
        raise ValueError(self.ctx.t('errors.bad_url'))

    async def _open(self, settings):
        """Connect and log in. Returns (session, websocket, Home Assistant version); raises with a readable message."""
        if not settings.get('token'):
            raise PermissionError(self.ctx.t('errors.no_token'))
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=10))
        try:
            ws = await session.ws_connect(self._ws_url(settings), ssl=None if settings.get('verify_ssl', True) else False,
                                          heartbeat=30, max_msg_size=0)
            hello = await asyncio.wait_for(ws.receive_json(), 10)
            if hello.get('type') != 'auth_required':
                raise ConnectionError(self.ctx.t('errors.not_ha'))
            await ws.send_json({'type': 'auth', 'access_token': settings['token']})
            answer = await asyncio.wait_for(ws.receive_json(), 10)
            if answer.get('type') == 'auth_invalid':
                raise PermissionError(self.ctx.t('errors.auth_invalid'))
            if answer.get('type') != 'auth_ok':
                raise ConnectionError(self.ctx.t('errors.not_ha'))
            return session, ws, answer.get('ha_version', '')
        except BaseException:
            await session.close()
            raise

    def _explain(self, error):
        if isinstance(error, (PermissionError, ValueError)):
            return str(error)
        if isinstance(error, (aiohttp.ClientConnectorCertificateError, ssl.SSLError)):
            return self.ctx.t('errors.tls')
        if isinstance(error, aiohttp.WSServerHandshakeError):
            return self.ctx.t('errors.handshake', status=error.status)
        if isinstance(error, aiohttp.ClientConnectorError):
            return self.ctx.t('errors.unreachable', url=self.ctx.settings.get('url', ''))
        if isinstance(error, asyncio.TimeoutError):
            return self.ctx.t('errors.timeout')
        return str(error) or type(error).__name__

    async def start(self):
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        await self._close()

    async def _close(self):
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ConnectionError(self.ctx.t('errors.offline')))
        self.pending.clear()
        if self.ws is not None:
            await self.ws.close()
        if self.session is not None:
            await self.session.close()
        self.ws = self.session = None

    async def _run(self):
        delay = 1
        while True:
            try:
                self.state, self.message = 'connecting', ''
                self.session, self.ws, self.version = await self._open(self.ctx.settings)
                reader = asyncio.create_task(self._read())
                states = await self._command({'type': 'get_states'})
                self.states = {s['entity_id']: s for s in states}
                await self._command({'type': 'subscribe_events', 'event_type': 'state_changed'})
                self.state = 'connected'
                self.message = self.ctx.t('status.connected', version=self.version, count=len(self.states))
                print(f'Home Assistant connected ({self.version}, {len(self.states)} entities)')
                delay = 1
                self.ctx.refresh()
                await reader                       # runs until the connection drops
                raise ConnectionError(self.ctx.t('errors.closed'))
            except asyncio.CancelledError:
                raise
            except PermissionError as e:           # a wrong token stays wrong; don't hammer the server
                self.state, self.message, delay = 'error', str(e), 60
            except Exception as e:
                self.state, self.message = 'error', self._explain(e)
            finally:
                await self._close()
            print(f'Home Assistant: {self.message}; retrying in {delay}s')
            self.ctx.refresh()                     # show the keys as offline
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    async def _read(self):
        async for message in self.ws:
            if message.type != aiohttp.WSMsgType.TEXT:
                continue
            data = message.json()
            for item in data if isinstance(data, list) else [data]:
                self._dispatch(item)

    def _dispatch(self, item):
        if item.get('type') == 'result':
            future = self.pending.pop(item.get('id'), None)
            if future and not future.done():
                if item.get('success'):
                    future.set_result(item.get('result'))
                else:
                    future.set_exception(RuntimeError((item.get('error') or {}).get('message', 'error')))
        elif item.get('type') == 'event':
            event = item.get('event') or {}
            if event.get('event_type') == 'state_changed':
                data = event.get('data') or {}
                entity, new = data.get('entity_id'), data.get('new_state')
                if new is None:
                    self.states.pop(entity, None)
                else:
                    self.states[entity] = new
                self.ctx.refresh({entity})

    async def _command(self, message, timeout=10):
        if self.ws is None or self.ws.closed:
            raise ConnectionError(self.ctx.t('errors.offline'))
        mid = self.next_id
        self.next_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[mid] = future
        await self.ws.send_json({**message, 'id': mid})
        return await asyncio.wait_for(future, timeout)

    async def _service(self, domain, service, entity, data=None):
        try:
            await self._command({'type': 'call_service', 'domain': domain, 'service': service,
                                 'target': {'entity_id': entity}, 'service_data': data or {}})
        except Exception as e:
            print(f'Home Assistant: {domain}.{service} {entity} failed: {self._explain(e)}')

    # --- the plugin interface
    def status(self):
        return {'state': self.state, 'message': self.message}

    def actions(self, kind, entry, event):
        entity = entry['entity']
        domain = entity.split('.')[0]
        if kind == 'ha.toggle':
            return [(f'Home Assistant: toggle {entity}', lambda: self._service(domain, 'toggle', entity))]
        if kind == 'ha.dimmer':
            if event == 'press':
                return [(f'Home Assistant: toggle {entity}', lambda: self._service('light', 'toggle', entity))]
            step = entry.get('step', 10) * (1 if event == 'right' else -1)
            return [(f'Home Assistant: {entity} brightness {step:+}%',
                     lambda: self._service('light', 'turn_on', entity, {'brightness_step_pct': step}))]
        return []   # ha.state only shows

    async def call(self, action, data):
        if action == 'test':
            try:
                session, ws, version = await self._open(data)
            except Exception as e:
                raise ValueError(self._explain(e))
            await ws.close()
            await session.close()
            return {'ok': True, 'message': self.ctx.t('status.test_ok', version=version)}
        if action == 'entities':
            if self.state != 'connected':
                raise ValueError(self.message or self.ctx.t('errors.offline'))
            domains = data.get('domains') or []
            found = [{'entity_id': entity, 'name': (s.get('attributes') or {}).get('friendly_name') or entity, 'state': s.get('state')}
                     for entity, s in self.states.items() if not domains or entity.split('.')[0] in domains]
            return sorted(found, key=lambda e: e['name'].lower())
        raise ValueError(f'unknown action {action}')

    # --- drawing
    def render(self, kind, entry):
        size = self.ctx.size
        big = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0))
        draw = ImageDraw.Draw(big)
        state = self.states.get(entry['entity']) or {}
        attributes = state.get('attributes') or {}
        online = self.state == 'connected'
        available = online and state.get('state') not in (None, 'unavailable', 'unknown')
        text_color = entry.get('color') or '#ffffff'
        value = None
        if kind == 'ha.toggle':
            on = available and state.get('state') == 'on'
            if entry['entity'].startswith('light.'):
                color = tuple(attributes.get('rgb_color') or LIGHT_ON) if on else OFF
                self._bulb(draw, size, on, color)
                if on and attributes.get('brightness') is not None:
                    value = f"{round(attributes['brightness'] / 2.55)}%"
            else:
                self._power(draw, size, on)
        elif kind == 'ha.state':
            pass   # the value is text, drawn below at full resolution
        img = big.resize((size, size), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        if kind == 'ha.state':
            shown = self._value(state) if available else '—'
            font_size = 64
            while font_size > 22 and self.ctx.font(font_size).getbbox(shown)[2] > size - 24:
                font_size -= 2
            draw.text((size / 2, size / 2 - 14), shown, font=self.ctx.font(font_size), fill=text_color, anchor='mm')
        if value:
            draw.text((size - 14, 16), value, font=self.ctx.font(22), fill=text_color, anchor='ra')
        title = str(entry.get('title') or attributes.get('friendly_name') or entry['entity'])
        font_size = 28
        while font_size > 16 and self.ctx.font(font_size).getbbox(title)[2] > size - 16:
            font_size -= 1
        draw.text((size / 2, size - 20), title, font=self.ctx.font(font_size), fill=text_color, anchor='mm')
        if not online:
            self._badge(draw, size, '!')
        elif not available:
            self._badge(draw, size, '?')
        return img

    @staticmethod
    def _value(state):
        text = str(state.get('state', ''))
        unit = (state.get('attributes') or {}).get('unit_of_measurement')
        try:
            number = float(text)
            text = f'{number:.0f}' if abs(number) >= 100 or number == int(number) else f'{number:.1f}'
        except ValueError:
            pass
        return f'{text} {unit}' if unit else text

    @staticmethod
    def _bulb(draw, size, on, color):
        cx, cy, r = size * S / 2, size * S * 0.36, size * S * 0.2
        if on:
            for k in range(3, 0, -1):    # a soft glow around a light that is on
                g = r + k * 9 * S
                draw.ellipse([cx - g, cy - g, cx + g, cy + g], fill=color + (60,))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
        else:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (255,), width=6 * S)
        base = (210, 210, 218, 255) if on else color + (255,)
        w = r * 0.55
        draw.rounded_rectangle([cx - w, cy + r * 0.92, cx + w, cy + r * 1.42], radius=4 * S, fill=base)
        draw.rounded_rectangle([cx - w * 0.7, cy + r * 1.5, cx + w * 0.7, cy + r * 1.75], radius=3 * S, fill=base)

    @staticmethod
    def _power(draw, size, on):
        cx, cy, r = size * S / 2, size * S * 0.4, size * S * 0.22
        color = SWITCH_ON if on else OFF
        if on:
            draw.ellipse([cx - r - 12 * S, cy - r - 12 * S, cx + r + 12 * S, cy + r + 12 * S], fill=color + (255,))
        ink = (255, 255, 255, 255) if on else color + (255,)
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=300, end=600, fill=ink, width=7 * S)
        draw.line([cx, cy - r - 6 * S, cx, cy], fill=ink, width=7 * S)

    def _badge(self, draw, size, mark):
        """A red dot in the top right corner: '!' when Home Assistant is offline, '?' when the entity is unavailable."""
        x, y, r = size - 26, 26, 14
        draw.ellipse([x - r, y - r, x + r, y + r], fill=WARN)
        draw.text((x, y), mark, font=self.ctx.font(22), fill='#ffffff', anchor='mm')
