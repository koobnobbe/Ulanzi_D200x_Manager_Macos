"""D200X Manager: the program. The built app (macOS) and exe (Windows) start here; from source: python main.py.

    main.py                    the icon in the menu bar (macOS) or system tray (Windows); it runs the manager
    main.py --manager [config] the manager itself: the deck, the web interface and the plugins
    main.py --run script ...   run a Python script with the app's Python (Claude Code's status line on Windows)
"""
import asyncio
import runpy
import sys


def main():
    args = sys.argv[1:]
    if args[:1] == ['--manager']:
        sys.argv = [sys.argv[0]] + args[1:]
        import d200x_manager
        asyncio.run(d200x_manager.main())
    elif args[:1] == ['--run'] and len(args) > 1:
        sys.argv = args[1:]
        runpy.run_path(args[1], run_name='__main__')
    else:
        import tray
        tray.main()


if __name__ == '__main__':
    main()
