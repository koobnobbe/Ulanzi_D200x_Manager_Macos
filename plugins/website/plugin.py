"""Websites on the deck: a key opens a web page, in the default browser or a chosen one, and shows the site's icon.

The icon comes from the site itself (apple-touch-icon, <link rel="icon"> or /favicon.ico), fetched once per host
and kept in .cache/favicons/<host>.png. Until then, or when a site has none, the key shows the first letter of
the site on a tile in a color of its own.
"""
import asyncio
import hashlib
import io
import os
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import aiohttp
from PIL import Image, ImageDraw

import system
from plugins import PROJECT_DIR, Plugin

CACHE_DIR = os.path.join(PROJECT_DIR, '.cache', 'favicons')
BROWSERS = {'safari': 'Safari', 'chrome': 'Google Chrome', 'firefox': 'Firefox', 'arc': 'Arc',
            'edge': 'Microsoft Edge', 'brave': 'Brave Browser'}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                         'Version/18.0 Safari/605.1.15',
           'Accept': 'text/html,application/xhtml+xml,image/avif,image/webp,image/png,*/*;q=0.8',
           'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8'}
TILE = (37, 22, 160, 145)      # as the icons of the libraries: a 123 px tile, the title below it
WHITE = (255, 255, 255)


def normalize(url):
    """The URL to open: 'example.com/x' gets https://. Returns None when it is not a web address."""
    url = str(url or '').strip()
    if url and not re.match(r'[a-z][a-z0-9+.-]*://', url, re.I):
        url = 'https://' + url
    parts = urlsplit(url)
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or ' ' in url:
        return None
    return url


def site(url):
    """'example.com' for https://www.example.com/x: the name shown on a key."""
    host = urlsplit(url).hostname or ''
    return host[4:] if host.startswith('www.') else host


def host_of(url):
    """'www.example.com' for https://www.example.com/x: where the icon is fetched (some sites only answer on www)."""
    return (urlsplit(url).hostname or '').lower()


class IconLinks(HTMLParser):
    """The <link rel="...icon..."> tags of a page, as (score, href); a higher score is a better icon."""

    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag != 'link':
            return
        attrs = dict(attrs)
        rel = (attrs.get('rel') or '').lower()
        href = attrs.get('href')
        if 'icon' not in rel or not href or href.lower().split('?')[0].endswith('.svg') or 'mask-icon' in rel:
            return
        sizes = [int(n) for n in re.findall(r'(\d+)x\d+', attrs.get('sizes') or '')]
        score = max(sizes) if sizes else (180 if 'apple-touch-icon' in rel else 32)
        self.found.append((score, href))


class Website(Plugin):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.icons = {}          # host -> Image, or None when the site has none
        self.fetching = {}       # host -> task
        self.loop = None

    async def start(self):
        # render() is also called from the web server's thread; fetches always start on this loop
        self.loop = asyncio.get_running_loop()

    async def stop(self):
        for task in self.fetching.values():
            if task:
                task.cancel()

    # --- the plugin interface
    def validate(self, kind, entry):
        if not normalize(entry.get('url')):
            return self.ctx.t('errors.bad_url', url=entry.get('url'))
        return None

    def actions(self, kind, entry, event):
        url = normalize(entry.get('url'))
        if not url:
            return []
        browser = entry.get('browser') if entry.get('browser') in BROWSERS else None
        # a browser that is not on this system (Safari on Windows) opens the default browser
        return [(f'open {url}' + (f' in {BROWSERS[browser]}' if browser else ''), lambda: system.open_url(url, browser))]

    async def call(self, action, data):
        if action == 'test':
            return {'ok': True, 'message': self.ctx.t('status.test_ok')}
        raise ValueError(f'unknown action {action}')

    def render(self, kind, entry):
        size = self.ctx.size
        url = normalize(entry.get('url'))
        host = site(url) if url else ''
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        icon = self.icon(host_of(url)) if url else None
        x0, y0, x1, y1 = TILE
        if icon is not None:
            # the site's icon on a white tile, so dark and transparent icons both show
            draw.rounded_rectangle(TILE, radius=26, fill=WHITE)
            inner = 84 if max(icon.size) >= 96 else 64     # small favicons are not blown up too much
            scale = inner / max(icon.size)
            icon = icon.resize((max(1, round(icon.width * scale)), max(1, round(icon.height * scale))), Image.LANCZOS)
            img.alpha_composite(icon, ((x0 + x1 - icon.width) // 2, (y0 + y1 - icon.height) // 2))
        else:
            digest = hashlib.md5(host.encode()).digest()
            hue = Image.new('HSV', (1, 1), (digest[0], 150, 210)).convert('RGB').getpixel((0, 0))
            draw.rounded_rectangle(TILE, radius=26, fill=hue)
            letter = (host[:1] or '?').upper()
            draw.text(((x0 + x1) / 2, (y0 + y1) / 2), letter, font=self.ctx.font(70), fill=WHITE, anchor='mm')
        title = str(entry.get('title') or host or self.ctx.t('render.no_url'))
        font_size = 30
        while font_size > 20 and self.ctx.font(font_size).getbbox(title)[2] > size - 10:
            font_size -= 1
        while len(title) > 4 and self.ctx.font(font_size).getbbox(title)[2] > size - 10:
            title = title[:-3].rstrip('.') + '..'     # the deck's font has no ellipsis
        draw.text((size / 2, 192), title, font=self.ctx.font(font_size), fill=entry.get('color') or '#ffffff', anchor='ms')
        return img

    # --- icons
    def icon(self, host):
        """The cached icon of a host, or None (then a fetch starts in the background)."""
        if host in self.icons:
            return self.icons[host]
        path = os.path.join(CACHE_DIR, host + '.png')
        if os.path.isfile(path):
            try:
                self.icons[host] = Image.open(path).convert('RGBA')
                return self.icons[host]
            except OSError:
                pass
        if host not in self.fetching and self.loop and not self.loop.is_closed():
            self.fetching[host] = None
            self.loop.call_soon_threadsafe(self._start_fetch, host)
        return None

    def _start_fetch(self, host):
        self.fetching[host] = self.loop.create_task(self._fetch(host))

    async def _fetch(self, host):
        try:
            icon = await self._find_icon(f'https://{host}/')
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f'website: no icon for {host}: {e}')
            icon = None
        self.icons[host] = icon
        if icon is not None:
            os.makedirs(CACHE_DIR, exist_ok=True)
            icon.save(os.path.join(CACHE_DIR, host + '.png'))
        self.ctx.refresh()

    async def _find_icon(self, page):
        async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as session:
            candidates = []
            try:
                async with session.get(page) as response:
                    base = str(response.url)
                    # a page that sent us elsewhere (a cookie wall, a login) has that other site's icon
                    if site(base) != site(page):
                        base = page
                    elif response.status == 200 and 'html' in response.headers.get('Content-Type', ''):
                        parser = IconLinks()
                        parser.feed((await response.content.read(512 * 1024)).decode('utf-8', 'replace'))
                        candidates = [urljoin(base, href) for _, href in sorted(parser.found, reverse=True)]
            except (aiohttp.ClientError, asyncio.TimeoutError):
                base = page
            candidates += [urljoin(base, '/apple-touch-icon.png'), urljoin(base, '/favicon.ico')]
            for url in dict.fromkeys(candidates):
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue
                        data = await response.content.read(2 * 1024 * 1024)
                    return self._decode(data)
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
                    continue
        return None

    @staticmethod
    def _decode(data):
        """The largest image in a PNG, JPEG or ICO file, as RGBA. Raises OSError for anything else."""
        image = Image.open(io.BytesIO(data))
        if image.format == 'ICO':
            image.size = max(image.ico.sizes())
        image = image.convert('RGBA')
        if image.width < 16 or image.height < 16:
            raise OSError('icon too small')
        return image
