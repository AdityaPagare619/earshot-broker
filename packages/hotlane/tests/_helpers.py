"""Shared fixtures for hotlane tests. Not a test module (underscore prefix)."""

from hotlane import (
    ExposureLedger,
    GeneralizationChain,
    Signal,
    TableRow,
    initial_ledger,
    logit,
)


def make_chain(lang="en"):
    return GeneralizationChain(
        depths=("d4 text", "d3 text", "d2 text", "d1 text"),
        renditions={lang: ("d4 text", "d3 text", "d2 text", "d1 text")},
    )


def make_row(item_id="itm_1", sensitivity=0.9, clearance=None, version=1):
    return TableRow(
        item_id=item_id,
        sensitivity=sensitivity,
        clearance=dict(clearance) if clearance else {"priya": 4},
        chain=make_chain(),
        version=version,
    )


def sig(kind, person=None, at=0.0, **kw):
    return Signal(kind=kind, person=person, at=at, **kw)


# A standard household: owner priya (usually home), mom (guest), kid maya.
PRIORS = {
    "priya": logit(0.9),
    "mom": logit(0.3),
    "maya": logit(0.5),
}
