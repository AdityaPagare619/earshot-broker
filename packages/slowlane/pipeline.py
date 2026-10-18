"""Stage 1 pipeline orchestration (S1).

process_item(): quarantine -> understand -> render -> verify (retry once) ->
template fallback -> compile. Every step is a pure function of its inputs
except the store transitions, which are recorded.

The pipeline never raises on content: failures produce QuarantineResult with
the item left QUARANTINED (fail private). The only exceptions are programming
errors (contract violations between stages).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from . import compiler as compiler_mod
from .models import (
    COMPILED, DraftChain, GeneralizationChain, Item, RenderInput,
    SecrecyEdge, TableRow, UnderstandOutput,
)
from .quarantine import QuarantineStore
from .render import RenderBackend, TemplateRenderBackend
from .seam import project_for_hotlane, projection_bytes
from .understand import FixtureUnderstander
from .verifier import TopicLexicon, Verdict, verify


@dataclass(frozen=True)
class PipelineResult:
    item_id: str
    ok: bool
    row: TableRow | None
    backend_used: str       # "fixture-template" | "llm" | "none"
    verify_failures: Tuple[str, ...]
    attempts: int


def _to_chain(draft: DraftChain) -> GeneralizationChain:
    return GeneralizationChain(depths=draft.depths, renditions=draft.renditions)


def process_item(store: QuarantineStore,
                 table_compiler: compiler_mod.TableCompiler,
                 item_id: str,
                 text_hint: str,
                 render_input: RenderInput,
                 edges: Tuple[SecrecyEdge, ...],
                 role_defaults: Dict[str, int],
                 roles: Dict[str, str],
                 lexicon: TopicLexicon,
                 version: int,
                 renderer: RenderBackend | None = None,
                 understander: FixtureUnderstander | None = None,
                 quasi: Tuple[str, str, str] = ("", "", ""),
                 history: List[Tuple[str, str, str, int]] | None = None,
                 ) -> PipelineResult:
    """Run one item through Stage 1. The item must already be QUARANTINED
    (ingested via store.ingest)."""
    renderer = renderer or TemplateRenderBackend()
    understander = understander or FixtureUnderstander(lexicon)
    item = store.get(item_id)

    understand: UnderstandOutput = understander.understand(item, text_hint)

    failures: Tuple[str, ...] = ()
    attempts = 0
    draft = None
    verdict = None
    for attempt in (1, 2):
        attempts = attempt
        draft = renderer.draft_chain(render_input)
        verdict = verify(draft, understand, lexicon, quasi, history)
        failures = verdict.failures
        if verdict.passed:
            break
        # attempt 2 is the retry; after two failures we fall back to templates
        # (which are themselves verified — defense in depth, not trust)
    assert draft is not None and verdict is not None

    backend_used = renderer.name
    if not verdict.passed:
        # Template fallback: the fixture backend IS the template backend, so
        # for the fixture this is a re-verify; for a future LLM backend this
        # is the boring-template safety net.
        fallback = TemplateRenderBackend()
        draft = fallback.draft_chain(render_input)
        verdict = verify(draft, understand, lexicon, quasi, history)
        failures = verdict.failures
        backend_used = f"{renderer.name}+template-fallback"
        if not verdict.passed:
            # Even templates failed (should not happen): item stays
            # QUARANTINED. Fail private, always.
            return PipelineResult(item_id=item_id, ok=False, row=None,
                                  backend_used=backend_used,
                                  verify_failures=failures, attempts=attempts)

    chain = _to_chain(draft)
    store.transition(item_id, COMPILED)
    compiled_item = store.get(item_id)
    row = table_compiler.compile(compiled_item, understand, edges,
                                 role_defaults, roles, chain, verdict, version)
    return PipelineResult(item_id=item_id, ok=True, row=row,
                          backend_used=backend_used,
                          verify_failures=failures, attempts=attempts)
