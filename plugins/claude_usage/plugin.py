"""Claude usage on the deck: how much of the session (5 hour) and weekly limits of your Claude plan is used.

It reads the same numbers Claude Code shows in its "Account & usage" panel, from GET /api/oauth/usage on
api.anthropic.com, with the login Claude Code keeps in the macOS Keychain ("Claude Code-credentials").
It never refreshes or changes that login: when the token has expired it waits until Claude Code has renewed it.
"""
import asyncio
import json
import os
import subprocess
import time
from datetime import datetime, timezone

import aiohttp
from PIL import Image, ImageDraw

from plugins import Plugin

USAGE_URL = 'https://api.anthropic.com/api/oauth/usage'
KEYCHAIN_SERVICE = 'Claude Code-credentials'
CREDENTIALS_FILE = os.path.expanduser('~/.claude/.credentials.json')   # used by Claude Code where there is no Keychain
BAR = (47, 111, 224)          # the blue of Claude Code's usage bars
BAR_HIGH = (240, 160, 50)     # from 75%
BAR_FULL = (235, 87, 87)      # from 90%
TRACK = (70, 70, 84)
WARN = (255, 105, 97)


class LoginError(Exception):
    pass


def read_login():
    """Claude Code's OAuth access token and when it expires (epoch seconds). Raises LoginError."""
    raw = None
    try:
        result = subprocess.run(['security', 'find-generic-password', '-s', KEYCHAIN_SERVICE, '-w'],
                                capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            raw = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if raw is None and os.path.isfile(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as fp:
            raw = fp.read()
    if not raw:
        raise LoginError('no_login')
    try:
        login = json.loads(raw).get('claudeAiOauth') or {}
    except ValueError:
        raise LoginError('no_login')
    if not login.get('accessToken'):
        raise LoginError('no_login')
    return login['accessToken'], (login.get('expiresAt') or 0) / 1000


def resets_in(text):
    """'14m', '3h 20m' or '3d' until an ISO time, like Claude Code shows it."""
    try:
        at = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return ''
    minutes = max(0, int((at - datetime.now(timezone.utc)).total_seconds() // 60))
    if minutes < 60:
        return f'{minutes}m'
    if minutes < 24 * 60:
        return f'{minutes // 60}h {minutes % 60}m' if minutes % 60 else f'{minutes // 60}h'
    return f'{minutes // (24 * 60)}d'


class ClaudeUsage(Plugin):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.usage = {}
        self.state, self.message = 'connecting', ''
        self.fetched_at = 0
        self.wait_until = 0         # after a 429: don't ask again before this time
        self.tasks = []

    def _interval(self):
        try:
            return max(60, float(self.ctx.settings.get('interval', 300)))
        except (TypeError, ValueError):
            return 300

    async def start(self):
        self.tasks = [asyncio.create_task(self._poll()), asyncio.create_task(self._tick())]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _poll(self):
        while True:
            await self.fetch()
            await asyncio.sleep(self._interval())

    async def _tick(self):
        # "resets in 14m" changes every minute, also between two fetches
        while True:
            await asyncio.sleep(60)
            self.ctx.refresh()

    async def fetch(self):
        if time.time() < self.wait_until:
            return
        try:
            token, expires = await asyncio.to_thread(read_login)
            if expires and expires < time.time():
                raise LoginError('expired')
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(USAGE_URL, headers={'Authorization': f'Bearer {token}', 'anthropic-beta': 'oauth-2025-04-20',
                                                           'Content-Type': 'application/json', 'User-Agent': 'd200x-manager'}) as response:
                    if response.status == 401:
                        raise LoginError('rejected')
                    if response.status == 429:
                        wait = int(response.headers.get('retry-after') or 300)
                        self.wait_until = time.time() + min(max(wait, 60), 3600)
                        raise RuntimeError(self.ctx.t('errors.rate_limited', minutes=max(1, wait // 60)))
                    if response.status != 200:
                        raise RuntimeError(self.ctx.t('errors.http', status=response.status))
                    self.usage = await response.json()
        except LoginError as e:
            self.state, self.message = 'error', self.ctx.t(f'errors.{e}')
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self.state, self.message = 'error', self.ctx.t('errors.unreachable')
        except Exception as e:
            self.state, self.message = 'error', str(e) or type(e).__name__
        else:
            self.fetched_at = time.time()
            self.state = 'connected'
            self.message = self.ctx.t('status.updated', time=datetime.now().strftime('%H:%M'))
        self.ctx.refresh()

    # --- the plugin interface
    def status(self):
        return {'state': self.state, 'message': self.message}

    def actions(self, kind, entry, event):
        # a press fetches right away, but not more often than every 30 seconds
        if time.time() - self.fetched_at < 30:
            return []
        return [('Claude usage: refresh', self.fetch)]

    async def call(self, action, data):
        if action == 'test':
            await self.fetch()
            if self.state != 'connected':
                raise ValueError(self.message)
            five = (self.usage.get('five_hour') or {}).get('utilization')
            week = (self.usage.get('seven_day') or {}).get('utilization')
            return {'ok': True, 'message': self.ctx.t('status.test_ok', session=round(five or 0), week=round(week or 0))}
        if action == 'refresh':
            await self.fetch()
            return {'ok': self.state == 'connected', 'message': self.message}
        raise ValueError(f'unknown action {action}')

    def render(self, kind, entry):
        size = self.ctx.size
        window = entry.get('window', 'five_hour')
        limit = self.usage.get(window) or {}
        percent = limit.get('utilization')
        color = entry.get('color') or '#ffffff'
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        title = str(entry.get('title') or self.ctx.t(f'options.window.{window}'))
        # leave room for the error badge in the top right corner
        self._fit(draw, title, (size / 2 - (10 if self.state == 'error' else 0), 28), 26, size - (64 if self.state == 'error' else 20), color)
        shown = f'{round(percent)}%' if percent is not None else '-'   # the deck's font has no long dash
        self._fit(draw, shown, (size / 2, 84), 62, size - 24, color)
        # the bar, as in Claude Code's usage panel
        x0, x1, y0, y1 = 18, size - 18, 122, 136
        draw.rounded_rectangle([x0, y0, x1, y1], radius=7, fill=TRACK)
        if percent:
            fill = BAR_FULL if percent >= 90 else BAR_HIGH if percent >= 75 else BAR
            width = max(14, (x1 - x0) * min(percent, 100) / 100)
            draw.rounded_rectangle([x0, y0, x0 + width, y1], radius=7, fill=fill)
        when = resets_in(limit.get('resets_at')) if limit.get('resets_at') else ''
        footer = self.ctx.t('render.resets_in', time=when) if when else (self.ctx.t('render.no_limit') if self.usage and percent is None else '')
        if footer:
            self._fit(draw, footer, (size / 2, 164), 22, size - 20, '#a8a8b8')
        if self.state == 'error':
            r, cx, cy = 13, size - 22, 22
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WARN)
            draw.text((cx, cy), '!', font=self.ctx.font(20), fill='#ffffff', anchor='mm')
        return img

    def _fit(self, draw, text, center, size, width, color):
        while size > 14 and self.ctx.font(size).getbbox(text)[2] > width:
            size -= 1
        draw.text(center, text, font=self.ctx.font(size), fill=color, anchor='mm')
