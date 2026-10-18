"""Pareto runner: leakage vs owner utility across the four baseline policies.

All four policies run over IDENTICAL synthetic households and episodes. For
each policy we measure:
  leakage    = existence AUC, pooled over (household, secret, listener, day)
               triples. The listener hears only what was spoken in their
               presence. Target for sealed speech: ~= 0.5.
  inference  = secret-topic inference rate vs base rate (1/4).
  utility    = mean owner utility (voice when present + phone digest).
  friction   = cover-mode-when-actually-alone rate (cost of uncertainty).

Emits: points dict (JSON-serializable), an SVG scatter chart, and Markdown
table rows. Deterministic in (seed, n_households).
"""
from __future__ import annotations

from . import lexicon as L
from .households import generate_households
from .listener import AdversarialListener
from .metrics import auc_mann_whitney, base_rate, friction, owner_utility_day
from .policies import POLICIES

PHONE_FULL = {"sealed_speech": True, "v1_lattice": True,
              "native": False, "keyword": False}


def _run_policy(pname: str, households: tuple) -> dict:
    """Run one policy over all households. Returns per-episode (ep, spoken)."""
    pfn = POLICIES[pname]
    pairs = [(hh, ep, pfn(ep, hh)) for hh in households for ep in hh.episodes]
    return pairs


def _existence_auc(pairs) -> tuple:
    """Pooled AUC over (household, secret, listener, day).

    Label: the secret was present in an episode the listener attended.
    The listener scores only what they heard that day.
    """
    triples = []
    # regroup by household
    by_hh: dict = {}
    for hh, ep, sp in pairs:
        by_hh.setdefault(hh.name, (hh, []))[1].append((ep, sp))
    for hh, eps in by_hh.values():
        for secret in hh.secrets:
            for listener in hh.listener_candidates():
                if listener.role not in secret.non_audience_roles:
                    continue
                adv = AdversarialListener(listener.id, listener.role)
                by_day: dict = {}
                for ep, sp in eps:
                    by_day.setdefault(ep.day, []).append((ep, sp))
                for day, day_pairs in by_day.items():
                    attended = [(ep, sp) for ep, sp in day_pairs
                                if listener.id in ep.audience]
                    if not attended:
                        continue
                    label = any(
                        any(it.secret is not None and it.secret.id == secret.id
                            for it in ep.items)
                        for ep, _ in attended
                    )
                    heard = [(ep.language, sp.voice_text) for ep, sp in attended]
                    triples.append((adv.existence_score(heard), label))
    return auc_mann_whitney(triples), len(triples)


def _inference_rate(pairs) -> tuple:
    """Secret-topic inference rate vs base rate, per (household, secret,
    listener in non-audience)."""
    by_hh: dict = {}
    for hh, ep, sp in pairs:
        by_hh.setdefault(hh.name, (hh, []))[1].append((ep, sp))
    correct, total = 0, 0
    for hh, eps in by_hh.values():
        for secret in hh.secrets:
            for listener in hh.listener_candidates():
                if listener.role not in secret.non_audience_roles:
                    continue
                adv = AdversarialListener(listener.id, listener.role)
                heard = [(ep.language, sp.voice_text) for ep, sp in eps
                         if listener.id in ep.audience]
                if not heard:
                    continue
                if adv.guess_topic(heard) == secret.topic:
                    correct += 1
                total += 1
    return (correct / total if total else 0.0), total


def _utility(pairs, phone_full: bool) -> float:
    by_hh_day: dict = {}
    for hh, ep, sp in pairs:
        owner = next(p.id for p in hh.people if p.role == L.OWNER)
        by_hh_day.setdefault((hh.name, ep.day, owner),
                             []).append((ep, sp))
    vals = [owner_utility_day(v, owner, phone_full)
            for (_, _, owner), v in by_hh_day.items()]
    return sum(vals) / len(vals) if vals else 1.0


def _friction(pairs) -> float:
    flat = [(ep, sp) for _, ep, sp in pairs]
    owners = {}
    for hh, ep, sp in pairs:
        owners.setdefault(hh.name, next(p.id for p in hh.people
                                        if p.role == L.OWNER))
    # friction per household then mean (households are the unit)
    vals = []
    for hhname, owner in owners.items():
        sub = [(ep, sp) for hh, ep, sp in pairs if hh.name == hhname]
        vals.append(friction(sub, owner))
    return sum(vals) / len(vals) if vals else 0.0


def run_pareto(seed: int = 7, n_households: int = 4,
               policies: dict | None = None) -> dict:
    """Run the full Pareto. `policies` overrides the four baselines
    (used by the negative-control test with a deliberately broken policy)."""
    policies = policies or POLICIES
    households = generate_households(n_households, seed)
    points = {}
    for pname, pfn in policies.items():
        pairs = [(hh, ep, pfn(ep, hh)) for hh in households
                 for ep in hh.episodes]
        auc, n_triples = _existence_auc(pairs)
        inf, n_inf = _inference_rate(pairs)
        util = _utility(pairs, PHONE_FULL.get(pname, False))
        fric = _friction(pairs)
        points[pname] = {
            "leakage_auc": round(auc, 4),
            "auc_triples": n_triples,
            "inference_rate": round(inf, 4),
            "inference_base_rate": round(base_rate(len(L.TOPICS)), 4),
            "inference_n": n_inf,
            "owner_utility": round(util, 4),
            "friction": round(fric, 4),
        }
    return {
        "seed": seed,
        "n_households": n_households,
        "days_per_household": 30,
        "episodes_per_household": 60,
        "listener": "keyword fixture (LOWER BOUND on adversary strength)",
        "points": points,
    }


# ---------------------------------------------------------------------------
# SVG chart (stdlib string templating — no matplotlib).
# ---------------------------------------------------------------------------
def pareto_svg(report: dict, width: int = 640, height: int = 420) -> str:
    pad_l, pad_r, pad_t, pad_b = 70, 30, 40, 60
    x0, x1 = 0.45, 1.02   # leakage AUC axis
    y0, y1 = 0.0, 1.05    # utility axis

    def X(v):
        return pad_l + (v - x0) / (x1 - x0) * (width - pad_l - pad_r)

    def Y(v):
        return height - pad_b - (v - y0) / (y1 - y0) * (height - pad_t - pad_b)

    colors = {"native": "#f4738a", "keyword": "#e8b34b",
              "v1_lattice": "#9a8cff", "sealed_speech": "#5fd08a"}
    labels = {"native": "native (says everything)",
              "keyword": "keyword filter",
              "v1_lattice": "v1 4-level lattice",
              "sealed_speech": "sealed speech"}

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" font-family="Inter,Segoe UI,sans-serif">',
         f'<rect width="{width}" height="{height}" fill="#11141c" rx="12"/>',
         f'<text x="{width/2}" y="24" text-anchor="middle" fill="#eef1f8" '
         f'font-size="15" font-weight="700">Privacy Pareto: leakage vs owner '
         f'utility (seed {report["seed"]})</text>']
    # chance line at AUC 0.5
    s.append(f'<line x1="{X(0.5)}" y1="{pad_t}" x2="{X(0.5)}" '
             f'y2="{height-pad_b}" stroke="#6b7390" stroke-dasharray="5,4"/>')
    s.append(f'<text x="{X(0.5)+6}" y="{pad_t+14}" fill="#6b7390" '
             f'font-size="11">chance (AUC 0.5)</text>')
    # axes
    s.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" '
             f'y2="{height-pad_b}" stroke="#232a3d"/>')
    s.append(f'<line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" '
             f'y2="{height-pad_b}" stroke="#232a3d"/>')
    for v in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        s.append(f'<text x="{X(v)}" y="{height-pad_b+18}" text-anchor="middle" '
                 f'fill="#6b7390" font-size="11">{v:.1f}</text>')
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        s.append(f'<text x="{pad_l-8}" y="{Y(v)+4}" text-anchor="end" '
                 f'fill="#6b7390" font-size="11">{v:.2f}</text>')
    s.append(f'<text x="{(width)/2}" y="{height-12}" text-anchor="middle" '
             f'fill="#9aa3b8" font-size="12">leakage: existence AUC '
             f'(lower is better)</text>')
    s.append(f'<text x="18" y="{height/2}" text-anchor="middle" '
             f'fill="#9aa3b8" font-size="12" transform="rotate(-90 18 '
             f'{height/2})">owner utility (higher is better)</text>')
    # points
    for pname, pt in report["points"].items():
        cx, cy = X(pt["leakage_auc"]), Y(pt["owner_utility"])
        c = colors[pname]
        s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="{c}" '
                 f'fill-opacity="0.85" stroke="#0b0d12" stroke-width="2"/>')
        s.append(f'<text x="{cx+14:.1f}" y="{cy+4:.1f}" fill="{c}" '
                 f'font-size="12" font-weight="600">{labels[pname]} '
                 f'({pt["leakage_auc"]:.2f}, {pt["owner_utility"]:.2f})</text>')
    s.append('</svg>')
    return "\n".join(s)


def pareto_markdown(report: dict) -> str:
    lines = ["| policy | leakage (AUC) | inference rate | owner utility | friction |",
             "|---|---|---|---|---|"]
    for pname, pt in report["points"].items():
        lines.append(
            f"| {pname} | {pt['leakage_auc']:.3f} | {pt['inference_rate']:.3f} "
            f"(base {pt['inference_base_rate']:.2f}) | {pt['owner_utility']:.3f} "
            f"| {pt['friction']:.3f} |")
    lines.append("")
    lines.append(f"seed={report['seed']}, households={report['n_households']}, "
                 f"listener: {report['listener']}")
    return "\n".join(lines)
