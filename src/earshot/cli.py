"""earshot.cli — entry-point functions for the console scripts.

Installed as:
    earshot-demo    5-beat sealed-speech demo (<60s, [SIMULATOR]/[FIXTURE] labeled)
    earshot-server  real MCP gateway (Streamable HTTP, spec 2025-11-25)
    earshot-sim     independent Echo-class web host (simulated, honesty banner)
    earshot         help + subcommand dispatcher
"""

from __future__ import annotations

import sys


def demo(argv=None) -> int:
    """Run the 5-beat demo. Returns the process exit code."""
    from earshot.demo.five_beats import main

    return main(argv)


def server(argv=None) -> int:
    """Run the MCP gateway. Returns the process exit code."""
    from earshot.gateway.mcp.server import main

    return main(argv)


def sim(argv=None) -> int:
    """Run the controlled web host simulator. Returns the process exit code."""
    from earshot.simulator.host import main

    return main(argv)


_COMMANDS = {
    "demo": ("run the 5-beat sealed-speech demo", demo),
    "server": ("run the MCP gateway (Streamable HTTP, spec 2025-11-25)", server),
    "sim": ("run the independent Echo-class simulator", sim),
}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("earshot — a private task broker for Alexa+")
        print()
        print("usage: earshot <command> [args]")
        print()
        for name, (desc, _) in _COMMANDS.items():
            print(f"  {name:<10} {desc}")
        print()
        print("Or use the dedicated entry points: earshot-demo, earshot-server, earshot-sim")
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in _COMMANDS:
        print(f"earshot: unknown command {cmd!r}", file=sys.stderr)
        print("try: earshot --help", file=sys.stderr)
        return 2
    return _COMMANDS[cmd][1](rest)


if __name__ == "__main__":
    sys.exit(main())
