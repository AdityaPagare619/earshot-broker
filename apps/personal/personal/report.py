"""Single-file HTML preview report — the phone-viewable trust artifact.

Renders exactly the preview dict (public / room-assumed / personal-full,
assumptions, counterfactual result). No external assets; works from file://.
"""
import html

_CSS = """
body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:#f6f5f2;color:#23252d}
.wrap{max-width:720px;margin:0 auto;padding:24px 18px 48px}
.eyebrow{font-size:11px;letter-spacing:.12em;color:#6b6f7c;margin:0 0 6px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:#6b6f7c;font-size:14px;margin:0 0 20px}
.card{background:#fff;border:1px solid #e2e0da;border-radius:10px;padding:14px 16px;margin:0 0 12px}
.card h2{font-size:13px;letter-spacing:.06em;margin:0 0 8px;color:#6b6f7c;text-transform:uppercase}
.card ul{margin:0;padding-left:18px}
.card li{margin:4px 0;font-size:15px}
.private{border-left:4px solid #c2410c}
.assump{font-size:13px;color:#6b6f7c}
.ok{color:#15803d;font-weight:700}
.bad{color:#b91c1c;font-weight:700}
.foot{font-size:12px;color:#9aa0ae;margin-top:18px}
"""


def render(preview_dict: dict, prove_dict: dict | None) -> str:
    def items(values):
        if not values:
            return "<li><i>(nothing released)</i></li>"
        return "".join(f"<li>{html.escape(v)}</li>" for v in values)

    counter = ""
    if prove_dict is not None:
        ok = prove_dict["counterfactual_ok"]
        cls = "ok" if ok else "bad"
        rows = "".join(
            f"<li>{html.escape(name)}: public projection "
            f"{'identical' if v['identical_to_baseline'] else 'CHANGED'}</li>"
            for name, v in prove_dict["variants"].items())
        counter = f"""
        <div class="card"><h2>Counterfactual proof</h2>
        <p>Hidden appointment changed (prenatal &rarr; therapy &rarr; removed).
        Public output: <span class="{cls}">{'UNCHANGED' if ok else 'CHANGED — BOUNDARY FAILED'}</span></p>
        <ul>{rows}</ul></div>"""

    assumptions = "".join(f"<li>{html.escape(a)}</li>" for a in preview_dict["assumptions"])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Earshot preview — {html.escape(preview_dict['request_ref'][:12])}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<p class="eyebrow">EARSHOT PERSONAL SURFACE &middot; WHAT EACH RECIPIENT SEES</p>
<h1>Day brief preview</h1>
<p class="sub">Request <code>{html.escape(preview_dict['request_ref'][:16])}&hellip;</code>
&middot; fixture data &middot; demo-grade auth</p>
<div class="card"><h2>Public &mdash; anyone, any host</h2><ul>{items(preview_dict['public'])}</ul></div>
<div class="card"><h2>Room &mdash; uncontrolled host (Profile A)</h2><ul>{items(preview_dict['room_uncontrolled_host'])}</ul></div>
<div class="card"><h2>Room &mdash; controlled host, &ldquo;alone&rdquo; assumed (Profile B demo)</h2><ul>{items(preview_dict['room_assumed_alone'])}</ul></div>
<div class="card private"><h2>Personal &mdash; owner only</h2><ul>{items(preview_dict['personal_full'])}</ul></div>
{counter}
<div class="card"><h2>Assumptions (stated, not proven)</h2><ul class="assump">{assumptions}</ul></div>
<p class="foot">Profile A (public persistent host) releases the public projection only &mdash; even when the
owner appears alone. This report contains fixture data.</p>
</div></body></html>
"""
