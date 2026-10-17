"""Texts of the app, read from lang/<language>.yaml.

The language is set with set_language() (from "ui: language:" in config.yaml, default en).
Keys missing from that file fall back to en.yaml.
A text can hold placeholders like {name}; t('key', name='x') fills them in.
"""
import os
import re

import yaml

import paths

LANG_DIR = paths.config('lang')
DEFAULT = 'en'

_language = DEFAULT
_texts = {}
_mtimes = None


def _flatten(tree, prefix=''):
    flat = {}
    for key, value in (tree or {}).items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f'{prefix}{key}.'))
        else:
            flat[f'{prefix}{key}'] = str(value)
    return flat


def languages():
    """[{'code': 'en', 'name': 'English'}, ...] for every file in lang/."""
    result = []
    for name in sorted(os.listdir(LANG_DIR)):
        code, ext = os.path.splitext(name)
        if ext != '.yaml':
            continue
        with open(os.path.join(LANG_DIR, name), encoding='utf-8') as fp:
            data = yaml.safe_load(fp) or {}
        result.append({'code': code, 'name': str((data.get('app') or {}).get('language_name') or code)})
    return result


def language():
    return _language


def set_language(code):
    """Use lang/<code>.yaml; an unknown or empty code falls back to the default."""
    global _language
    valid = isinstance(code, str) and re.fullmatch(r'[\w-]+', code)
    _language = code if valid and os.path.exists(os.path.join(LANG_DIR, f'{code}.yaml')) else DEFAULT


PLUGIN_DIR = paths.config('plugins')


def _files():
    """(path, key prefix) of every language file to merge: the app's, then each plugin's under plugin.<id>."""
    codes = list(dict.fromkeys([DEFAULT, _language]))
    files = [(os.path.join(LANG_DIR, f'{code}.yaml'), '') for code in codes]
    if os.path.isdir(PLUGIN_DIR):
        for plugin in sorted(os.listdir(PLUGIN_DIR)):
            files += [(os.path.join(PLUGIN_DIR, plugin, 'lang', f'{code}.yaml'), f'plugin.{plugin}.') for code in codes]
    return files


def texts():
    """All texts as {dotted.key: text}. Re-read when a language file changes, so edits show without a restart."""
    global _texts, _mtimes
    files = [(f, prefix) for f, prefix in _files() if os.path.exists(f)]
    mtimes = [(f, os.path.getmtime(f)) for f, _ in files]
    if mtimes != _mtimes:
        merged = {}
        for path, prefix in files:
            with open(path, encoding='utf-8') as fp:
                merged.update(_flatten(yaml.safe_load(fp), prefix))
        _texts, _mtimes = merged, mtimes
    return _texts


def t(key, **values):
    text = texts().get(key, key)
    for name, value in values.items():
        text = text.replace('{' + name + '}', str(value))
    return text
