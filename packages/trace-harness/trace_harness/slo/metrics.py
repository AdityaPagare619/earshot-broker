"""Metrics for the SLO lab. stdlib only.

- auc_mann_whitney: P(score(positive) > score(negative)) via ranks, tie-corrected.
- inference_rate: fraction of (secret, listener) pairs where the topic guess
  was correct, vs the base rate of 1/n_topics.
- owner_utility: mean over days of mean over items of the best depth the owner
  received (voice when present, phone digest otherwise), normalized by 4.
- friction: fraction of owner-actually-alone episodes answered in cover mode.
"""
from __future__ import annotations

from . import lexicon as L


def auc_mann_whitney(scores_labels: list) -> float:
    """scores_labels: [(score, label_bool)]. Returns AUC in [0, 1].

    Rank-based (Mann-Whitney U), with average ranks for ties. Deterministic.
    Returns 0.5 when either class is empty (no signal possible).
    """
    pos = sorted(s for s, y in scores_labels if y)
    neg = sorted(s for s, y in scores_labels if not y)
    n1, n2 = len(pos), len(neg)
    if n1 == 0 or n2 == 0:
        return 0.5
    # Average ranks over the pooled sorted scores.
    pooled = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    rank_sum_pos = 0.0
    i = 0
    n = len(pooled)
    while i < n:
        j = i
        while j < n and pooled[j][0] == pooled[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0  # 1-based average rank of the tie group
        for k in range(i, j):
            if pooled[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j
    u1 = rank_sum_pos - n1 * (n1 + 1) / 2.0
    return u1 / (n1 * n2)


def base_rate(n_topics: int) -> float:
    return 1.0 / n_topics


def owner_utility_day(pairs, owner_id: str, phone_full: bool) -> float:
    """Mean over items of the best depth the owner received that day.

    pairs: [(episode, spoken)] for one day. phone_full: whether this policy's
    phone digest carries full (d4) content for withheld items.
    """
    items = {}
    for ep, sp in pairs:
        owner_present = owner_id in ep.audience
        for it in ep.items:
            vd = sp.depths.get(it.id, 0)
            best = items.get(it.id, 0)
            if owner_present:
                best = max(best, vd)
            if sp.phone_sent and phone_full and vd < 4:
                best = max(best, 4)
            items[it.id] = best
    if not items:
        return 1.0
    return sum(items.values()) / (4.0 * len(items))


def friction(pairs, owner_id: str) -> float:
    """Fraction of owner-actually-alone episodes answered in cover mode.

    The measured cost of belief uncertainty. Ground-truth audience is used:
    this is about what actually happened, not what the policy believed.
    """
    alone = [(ep, sp) for ep, sp in pairs if set(ep.audience) == {owner_id}]
    if not alone:
        return 0.0
    covered = sum(1 for _, sp in alone if sp.mode == "cover")
    return covered / len(alone)
