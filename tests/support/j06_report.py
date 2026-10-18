"""J6 evidence reporter: every claim my suites make lands in evidence/ as JSON.

Each record: {suite, test, dossier_ref, observation, verdict, detail}.
Flushed via atexit so `python3 -m unittest discover` also produces evidence.
"""
import atexit
import datetime
import json
import os
import subprocess

from tests import EVIDENCE_DIR


def _kernel_sha():
    try:
        out = subprocess.run(
            ['git', 'log', '-1', '--format=%H', '--', 'packages/kernel/kernel.py'],
            capture_output=True, text=True, cwd=os.path.dirname(EVIDENCE_DIR),
            timeout=10)
        return out.stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


class Reporter:
    def __init__(self, suite):
        self.suite = suite
        self.records = []
        self._flushed = False
        atexit.register(self.flush)

    def record(self, test, dossier_ref, observation, verdict, detail=None):
        self.records.append({
            'suite': self.suite,
            'test': test,
            'dossier_ref': dossier_ref,
            'observation': observation,
            'verdict': verdict,
            'detail': detail or {},
        })

    def flush(self):
        if self._flushed:
            return
        self._flushed = True
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        payload = {
            'suite': self.suite,
            'generated_utc': datetime.datetime.now(
                datetime.timezone.utc).isoformat(),
            'kernel_sha': _kernel_sha(),
            'n_records': len(self.records),
            'records': self.records,
        }
        path = os.path.join(EVIDENCE_DIR, 'j06-%s-report.json' % self.suite)
        if not self.records:
            # Import/collection without execution (e.g. pytest --collect-only)
            # must never clobber a real evidence file with an empty report.
            try:
                with open(path) as f:
                    existing = json.load(f)
                if existing.get('records'):
                    return
            except (OSError, ValueError):
                pass
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2, sort_keys=True)
