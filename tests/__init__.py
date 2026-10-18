"""J6 test tree: paired-world + adversarial suites for the EARSHOT reference kernel.

Stdlib only. Run from the repo root:  python3 -m unittest discover -s tests -v
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KERNEL_DIR = os.path.join(_REPO_ROOT, 'packages', 'kernel')
if _KERNEL_DIR not in sys.path:
    sys.path.insert(0, _KERNEL_DIR)

EVIDENCE_DIR = os.path.join(_REPO_ROOT, 'evidence')
