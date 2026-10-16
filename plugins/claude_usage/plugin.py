"""Claude usage on the deck: how much of the session (5 hour) and weekly limits of your Claude plan is used.

Claude Code hands its status line the same numbers it shows in its "Account & usage" panel. statusline.py, set
as Claude Code's status line, saves them in .cache/claude_usage.json; this plugin reads that file. No network,
no login and no rate limits: the numbers are as fresh as the last message in any Claude Code session.
"""
import asyncio
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone

from PIL import Image, ImageDraw

from plugins import PROJECT_DIR, Plugin

DATA_FILE = os.path.join(PROJECT_DIR, '.cache', 'claude_usage.json')
STATUSLINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'statusline.py')
CLAUDE_SETTINGS = os.path.expanduser('~/.claude/settings.json')
BAR = (47, 111, 224)          # the blue of Claude Code's usage bars
BAR_HIGH = (240, 160, 50)     # from 75%
BAR_FULL = (235, 87, 87)      # from 90%
TRACK = (70, 70, 84)
WARN = (255, 105, 97)


def epoch(value):
    """resets_at as epoch seconds; Claude Code gives a number, the usage API an ISO time."""
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e12 else value
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def resets_in(at):
    """'14m', '3h 20m' or '3d' until epoch seconds, like Claude Code shows it."""
    minutes = max(0, int((at - time.time()) // 60))
    if minutes < 60:
        return f'{minutes}m'
    if minutes < 24 * 60:
        return f'{minutes // 60}h {minutes % 60}m' if minutes % 60 else f'{minutes // 60}h'
    return f'{minutes // (24 * 60)}d'


def statusline_command():
    if sys.platform == 'win32':
        # no system Python on Windows: the manager's own (the .venv's)
        return subprocess.list2cmdline([sys.executable, STATUSLINE])
    return f'/usr/bin/python3 {shlex.quote(STATUSLINE)}'


def install_statusline():
    """Set statusline.py as Claude Code's status line. Returns 'installed', 'present' or 'other' (left alone)."""
    try:
        with open(CLAUDE_SETTINGS, encoding='utf-8') as fp:
            settings = json.load(fp)
    except FileNotFoundError:
        settings = {}
    current = (settings.get('statusLine') or {}).get('command', '')
    if STATUSLINE in current:
        return 'present'
    if current:
        return 'other'
    settings['statusLine'] = {'type': 'command', 'command': statusline_command(), 'padding': 0}
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS), exist_ok=True)
    with open(CLAUDE_SETTINGS + '.tmp', 'w', encoding='utf-8') as fp:
        json.dump(settings, fp, indent=2, ensure_ascii=False)
        fp.write('\n')
    os.replace(CLAUDE_SETTINGS + '.tmp', CLAUDE_SETTINGS)
    return 'installed'


class ClaudeUsage(Plugin):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.limits = {}
        self.saved_at = 0
        self.mtime = None
        self.state, self.message = 'connecting', ''
        self.task = None

    async def start(self):
        self.load()
        self.task = asyncio.create_task(self._watch())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass

    async def _watch(self):
        # the file changes after every Claude Code message; "resets in 14m" changes every minute
        minute = time.time() // 60
        while True:
            await asyncio.sleep(2)
            changed = self.load()
            if changed or time.time() // 60 != minute:
                minute = time.time() // 60
                self.ctx.refresh()

    def load(self):
        """Read the data file when it changed. Returns True when the keys need redrawing."""
        try:
            mtime = os.path.getmtime(DATA_FILE)
        except OSError:
            mtime = None
        if mtime == self.mtime:
            return False
        self.mtime = mtime
        if mtime is None:
            self.limits = {}
            self.state, self.message = 'error', self.ctx.t('errors.no_data')
            return True
        try:
            with open(DATA_FILE, encoding='utf-8') as fp:
                data = json.load(fp)
            self.limits = data.get('rate_limits') or {}
            self.saved_at = data.get('saved_at') or mtime
        except (OSError, ValueError):
            return False    # half written; the next look gets it
        self.state = 'connected'
        self.message = self.ctx.t('status.updated', time=datetime.fromtimestamp(self.saved_at).strftime('%H:%M'))
        return True

    def window(self, name):
        """(percent or None, reset time or None) of a limit; a limit whose reset has passed is back at 0%."""
        limit = self.limits.get(name) or {}
        percent = limit.get('used_percentage', limit.get('utilization'))
        at = epoch(limit.get('resets_at')) if limit.get('resets_at') else None
        if at and at <= time.time():
            return 0, None
        return percent, at

    # --- the plugin interface
    def status(self):
        return {'state': self.state, 'message': self.message}

    def actions(self, kind, entry, event):
        return [('Claude usage: refresh', self._refresh_now)]

    def _refresh_now(self):
        self.mtime = None
        self.load()
        self.ctx.refresh()

    async def call(self, action, data):
        if action == 'test':
            result = await asyncio.to_thread(install_statusline)
            if result == 'other':
                raise ValueError(self.ctx.t('errors.other_statusline', command=statusline_command()))
            self._refresh_now()
            if self.state != 'connected':
                raise ValueError(self.ctx.t('status.installed' if result == 'installed' else 'errors.no_data'))
            five, _ = self.window('five_hour')
            week, _ = self.window('seven_day')
            return {'ok': True, 'message': self.ctx.t('status.test_ok', session=round(five or 0), week=round(week or 0),
                                                      time=datetime.fromtimestamp(self.saved_at).strftime('%H:%M'))}
        raise ValueError(f'unknown action {action}')

    def render(self, kind, entry):
        size = self.ctx.size
        name = entry.get('window', 'five_hour')
        percent, at = self.window(name)
        color = entry.get('color') or '#ffffff'
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        title = str(entry.get('title') or self.ctx.t(f'options.window.{name}'))
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
        footer = self.ctx.t('render.resets_in', time=resets_in(at)) if at else ''
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
