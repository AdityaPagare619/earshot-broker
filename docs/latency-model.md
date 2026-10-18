# Honest latency model (§11.3)

Worst-case exposure after a listener *physically* enters is the sum:

```
undetected entry duration
+ sensing delay
+ event transport delay
+ arbiter response delay
+ unflushable audio already buffered
```

## What was measured (evidence/latency.json)

Kernel-op latency, 20,000 iterations each, single-process CPython:

| op | p50 | p99 |
|---|---|---|
| `Label.allows` | 0.35 µs | 0.48 µs |
| `Label.join` | 0.92 µs | 1.36 µs |
| `Kernel.public_projection` | 0.69 µs | 1.25 µs |
| `Kernel.room_projection` | 0.99 µs | 1.83 µs |
| `Kernel.derive` | 2.02 µs | 8.48 µs |
| `Kernel.prepare` | 1.88 µs | 17.1 µs |
| `Kernel.redeem` | 1.18 µs | 1.72 µs |
| `Kernel.accept` | 0.81 µs | 1.00 µs |
| `Kernel.open_private` | 0.71 µs | 0.98 µs |

These bound the **arbiter response** term only — the decision itself is
microseconds. A fast kernel does not compensate for a blind camera.

## What was NOT measured (labeled, not hand-waved)

| term | status | reason |
|---|---|---|
| undetected entry duration | UNMEASURABLE-HERE | No physical sensor; could be unbounded (§11.3: "If entry is never detected, no finite stop bound exists") |
| sensing delay | UNMEASURABLE-HERE | No camera/person-count pipeline in this build |
| event transport delay | UNMEASURABLE-HERE | No sensor→arbiter channel; depends on deployment (local IPC vs network) |
| unflushable buffered audio | UNMEASURABLE-HERE | No audio pipeline; the renderer's chunk size sets this term |

## Reading the model correctly

1. The kernel term is ~6 orders of magnitude below the 500ms round-trip
   budget — it will never be the bottleneck. Anyone optimizing it further is
   tuning theater (principal-mindset: wrong proxy).
2. The dominant terms are all *physical*: how fast entry is detected and how
   much audio is already queued. The security property lives or dies on
   sensing + chunking, not on decision speed.
3. Smaller audio chunks shrink the last term but harm natural speech (§11.3) —
   a product tradeoff, not an engineering constant. The per-chunk
   `authorize_playback` check (arbiter.py) is where the tradeoff is enforced.
4. Measure the remaining terms on the actual test device before any stop-
   latency claim. Until then, the only honest statement is the sum above with
   four labeled unknowns.
