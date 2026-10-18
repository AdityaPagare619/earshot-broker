"""Render backends (S1).

The render interface is LLM-shaped: a real model backend implements
RenderBackend.draft_chain() with zero verifier changes. The shipped backend
is TemplateRenderBackend — boring templates, honestly labeled FIXTURE.

Design rule: the fixture is never "smart". A smart fixture is a liar. The
fixture produces deliberately non-specific drafts; the verifier still checks
them (defense in depth — even templates cross the verifier).
"""
from __future__ import annotations

import abc
from typing import Dict, Tuple

from .models import DraftChain, RenderInput

FIXTURE_BACKEND_NAME = "fixture-template"


class RenderBackend(abc.ABC):
    """LLM-shaped render interface. Implementations draft a generalization
    chain; the verifier decides whether it may live."""

    @abc.abstractmethod
    def draft_chain(self, render_input: RenderInput) -> DraftChain:
        """Draft (d4, d3, d2, d1) per language. UNVERIFIED — must cross the
        verifier before becoming a GeneralizationChain."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError


# Boring templates. d4/d3 are deliberately NON-specific in the fixture: the
# fixture never invents specifics it wasn't given. Specifics come from the
# real backend later — still verified.
_TEMPLATES: Dict[str, Dict[int, str]] = {
    "event": {
        4: "an appointment at {time}",
        3: "an appointment at {time}",
        2: "an appointment at {time}",
        1: "something this {daypart}",
    },
    "reminder": {
        4: "a reminder for {daypart}",
        3: "a reminder for {daypart}",
        2: "a reminder for {daypart}",
        1: "something this {daypart}",
    },
    "delivery": {
        4: "a package arriving {daypart}",
        3: "a package arriving {daypart}",
        2: "a package arriving {daypart}",
        1: "something arriving {daypart}",
    },
    "note": {
        4: "a note for {daypart}",
        3: "a note for {daypart}",
        2: "a note for {daypart}",
        1: "something this {daypart}",
    },
    "message_summary": {
        4: "a message to review {daypart}",
        3: "a message to review {daypart}",
        2: "a message to review {daypart}",
        1: "something this {daypart}",
    },
}

# Hindi (Devanagari) fixture templates — same boring semantics, labeled fixture.
_TEMPLATES_HI: Dict[str, Dict[int, str]] = {
    "event": {
        4: "{time} par ek appointment",
        3: "{time} par ek appointment",
        2: "{time} par ek appointment",
        1: "is {daypart} kuch hai",
    },
    "delivery": {
        4: "{daypart} ek package aa raha hai",
        3: "{daypart} ek package aa raha hai",
        2: "{daypart} ek package aa raha hai",
        1: "{daypart} kuch aa raha hai",
    },
}
_TEMPLATES_HI_DEVANAGARI: Dict[str, Dict[int, str]] = {
    "event": {
        4: "{time} पर एक अपॉइंटमेंट",
        3: "{time} पर एक अपॉइंटमेंट",
        2: "{time} पर एक अपॉइंटमेंट",
        1: "इस {daypart} कुछ है",
    },
    "delivery": {
        4: "{daypart} एक पैकेज आ रहा है",
        3: "{daypart} एक पैकेज आ रहा है",
        2: "{daypart} एक पैकेज आ रहा है",
        1: "{daypart} कुछ आ रहा है",
    },
}

_DAYPART_HI = {
    "morning": "सुबह", "afternoon": "दोपहर",
    "evening": "शाम", "night": "रात",
}


def _fill(template: str, render_input: RenderInput, daypart: str) -> str:
    return template.format(time=render_input.time_label, daypart=daypart)


class TemplateRenderBackend(RenderBackend):
    """FIXTURE backend: boring per-kind templates. No model, no invention.

    Every output is labeled fixture-template. A real LLM backend implements
    the same draft_chain() signature; the verifier cannot tell them apart —
    which is exactly the point of the dumb-LLM doctrine.
    """

    @property
    def name(self) -> str:
        return FIXTURE_BACKEND_NAME

    def draft_chain(self, render_input: RenderInput) -> DraftChain:
        kind = render_input.kind if render_input.kind in _TEMPLATES else "note"
        langs = render_input.langs or ("en",)
        renditions: Dict[str, Tuple[str, str, str, str]] = {}
        for lang in langs:
            if lang == "hi":
                table = _TEMPLATES_HI_DEVANAGARI.get(kind, _TEMPLATES_HI_DEVANAGARI["event"])
                daypart = _DAYPART_HI.get(render_input.daypart, render_input.daypart)
            elif lang == "hi-Latn":
                table = _TEMPLATES_HI.get(kind, _TEMPLATES_HI["event"])
                daypart = render_input.daypart
            else:  # en and everything else: English templates (documented)
                table = _TEMPLATES[kind]
                daypart = render_input.daypart
            depths = tuple(_fill(table[d], render_input, daypart) for d in (4, 3, 2, 1))
            renditions[lang] = depths
        depths_en = renditions.get("en", renditions[langs[0]])
        return DraftChain(depths=depths_en, renditions=renditions,
                          backend=FIXTURE_BACKEND_NAME)
