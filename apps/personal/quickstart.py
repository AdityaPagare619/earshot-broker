"""Shim: run the installed personal quickstart.

Prefer the entry point: `earshot personal-quickstart`.
Requires `pip install -e .` from the repo root first.
"""
import sys

try:
    from earshot.personal.quickstart import main
except ImportError:
    sys.exit("earshot is not installed. From the repo root, run: pip install -e .")

if __name__ == "__main__":
    sys.exit(main())
