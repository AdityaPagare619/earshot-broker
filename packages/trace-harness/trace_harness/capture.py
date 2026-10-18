"""Capture: run the same request script against a world, record the trace."""
import copy
from .adapters import TraceStep


def run_sequence(adapter, world) -> list:
    """Execute world's script through adapter; return the list of TraceSteps.

    "{receipt}" inside any arg string is replaced with the request_ref from
    the most recent prepare_day_brief step.
    """
    adapter.connect()
    try:
        steps = []
        receipt = None
        for raw_step in world.script:
            args = _substitute(copy.deepcopy(raw_step["args"]), receipt)
            step = adapter.call(raw_step["tool"], args)
            if (step.status == "ok" and raw_step["tool"] == "prepare_day_brief"
                    and isinstance(step.result, dict)):
                receipt = step.result.get("request_ref", receipt)
            steps.append(step)
        return steps
    finally:
        adapter.close()


def _substitute(args: dict, receipt) -> dict:
    if receipt is None:
        return args
    return {k: (v.replace("{receipt}", receipt) if isinstance(v, str) else v)
            for k, v in args.items()}
