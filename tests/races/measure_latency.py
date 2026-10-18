"""Measure kernel-op latency (the ONE §11.3 term measurable here).

Writes evidence/latency.json: p50/p99 per op over N iterations, with a machine
note. Everything else in the §11.3 sum is labeled UNMEASURABLE-HERE in
docs/latency-model.md — one measured number beats five invented ones.
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'packages', 'kernel'))
from kernel import Context, Fact, Kernel, Label  # noqa: E402

PRI = Label(frozenset({'priya'}), frozenset({'health'}))
SECRET = Fact('appointment', 'Prenatal visit, 15:40', PRI)
PUB = Label(frozenset({'*'}))
PUBLIC_FACT = Fact('weather', 'Rain is forecast.', PUB)
CTX = Context('house-a', 'priya', frozenset({'priya'}), 1, 100.0,
              True, True, True, 1)
N = 20000


def bench(fn):
    samples = []
    for _ in range(N):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)  # µs
    samples.sort()
    return {
        'n': N,
        'p50_us': round(samples[N // 2], 3),
        'p99_us': round(samples[int(N * 0.99)], 3),
        'max_us': round(samples[-1], 3),
    }


def main():
    k = Kernel()
    results = {
        'Label.allows': bench(lambda: PRI.allows(frozenset({'priya'}))),
        'Label.join': bench(lambda: PRI.join(PUB)),
        'Kernel.public_projection': bench(
            lambda: Kernel.public_projection((PUBLIC_FACT, SECRET))),
        'Kernel.room_projection': bench(
            lambda: Kernel.room_projection((SECRET,), CTX, 100.0)),
        'Kernel.derive': bench(
            lambda: Kernel.derive('x', 'y', (PUBLIC_FACT, SECRET))),
    }
    lease = Kernel.prepare(SECRET, CTX, 100.0)
    results['Kernel.prepare'] = bench(lambda: Kernel.prepare(SECRET, CTX, 100.0))
    results['Kernel.redeem'] = bench(lambda: Kernel.redeem(lease, CTX, 100.1))
    results['Kernel.accept'] = bench(
        lambda: k.accept('house-a', 'priya', 'rk', (SECRET,), 100.0))
    r = k.accept('house-a', 'priya', 'rk2', (SECRET,), 100.0)['receipt']
    results['Kernel.open_private'] = bench(
        lambda: k.open_private(r, 'house-a', 'priya', True, 100.0))

    out = {
        'machine': os.uname().nodename + ' / ' + os.uname().machine,
        'python': sys.version.split()[0],
        'ops': results,
        'note': ('Single-process CPython; kernel ops only. These bound the '
                 'arbiter-response term of the §11.3 latency sum, nothing else.'),
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..', 'evidence', 'latency.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: (v['p50_us'], v['p99_us']) for k, v in results.items()},
                     indent=2))
    print('wrote', path)


if __name__ == '__main__':
    main()
