#!/usr/bin/env python3
"""Status line for Claude Code that also passes the plan limits on to the Claude usage plugin.

Claude Code runs this after each message with a JSON object on stdin; its "rate_limits" holds the same numbers
as the "Account & usage" panel. They are saved in the file named as first argument (the plugin's claude_usage.json
in the manager's cache), and one line is
printed for Claude Code's status line. Set up by the plugin's "Test connection" (statusLine in ~/.claude/settings.json).
Plain Python 3, no packages: Claude Code starts it with /usr/bin/python3.
"""
import json
import os
import sys
import time

DATA_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.cache', 'claude_usage.json')


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    limits = data.get('rate_limits')
    if limits:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE + '.tmp', 'w') as fp:
            json.dump({'saved_at': time.time(), 'rate_limits': limits}, fp)
        os.replace(DATA_FILE + '.tmp', DATA_FILE)
    parts = [(data.get('model') or {}).get('display_name') or '']
    for key, name in (('five_hour', '5h'), ('seven_day', '7d')):
        percent = ((limits or {}).get(key) or {}).get('used_percentage')
        if percent is not None:
            parts.append(f'{name} {round(percent)}%')
    print(' · '.join(p for p in parts if p))


if __name__ == '__main__':
    main()
