"""J6 test tree: paired-world + adversarial suites for the EARSHOT reference kernel.

Stdlib only. Run from the repo root:  python3 -m unittest discover -s tests -v
"""
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVIDENCE_DIR = os.path.join(_REPO_ROOT, 'evidence')
