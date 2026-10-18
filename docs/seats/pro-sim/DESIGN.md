# pro-sim DESIGN — simulator UX polish

## The walk-in story (first 30 seconds)

A Devpost judge lands on `http://127.0.0.1:8734/` with 90 seconds and zero context.

- **0–3s**: A bold amber/black banner says **SIMULATED — not a live Alexa+ device**.
  No squinting, no footnote. They know what they're looking at before anything else.
- **3–10s**: One hero button: **▶ Replay the night (40 seconds)**. The caption
  underneath tells them exactly what will happen: "Priya asks for her day plan.
  Mom walks in mid-sentence. Watch what the speaker does — and doesn't do."
- **10–40s**: The night plays itself. The speaker briefs; a beat-by-beat narration
  strip explains each moment *as the real arbiter events fire* (event-driven off
  `/api/events`, never timers — the narration is honest instrumentation):
  1. "Briefing the room — every sentence is a lease, gated per-segment."
  2. "Mom walked in. Speaker stopped FIRST, then epoch advanced, pending grants invalidated."
  3. "What the room heard: 'Paused — moved to your phone.' Nothing else. No count, no hint."
  4. "The phone synced silently. Unlock it — the exact plan is there."
- **40–60s**: The judge is invited to try: "Now say 'make room for a twenty-minute
  call' — watch it adapt using the private commitment *without naming it*."
  Plus a manual **Mom enters** button made unmissable for those who skip the script.

## Changes (all in apps/simulator/ui/index.html + tiny host.py touch)

1. **Banner**: dark → amber/black high-contrast strip, "SIMULATED" chip, 16px.
   Unmissable on 390px too.
2. **Hero walk-in card**: replaces the current flat "▶ Run walk-in demo" row. Big
   primary button + 2-line plain-English caption + estimated duration.
3. **Narration strip** (`#storyline`): one-part-at-a-time captions driven by real
   events: `tool_call(prepare_day_brief)` → beat 1; `AUDIENCE_CHANGED` with mom →
   beat 2 (+ stopped line); pollOutput `stopped` → beat 3; any `/api/phone` unlock →
   beat 4. No event → no caption (honest).
4. **Mom moment**: dedicated large "🚪 Mom walks in" button (separate from the
   small guest controls); on fire, the room strip flashes amber and the narration
   names the epoch + invalidated grants from the real event detail.
5. **Mobile**: `@media (max-width:640px)` — stack grid to one column, phone panel
   below transcript, device shrinks, controls full-width. Verify at 390px.
6. **Anti-generic pass**: semantic type tokens, no template gray; the Echo device
   keeps its identity. Copy via mrstev3n lens: short, human, no jargon.

## Storytelling skill applied

playthru (diip3sh): a scripted self-playing walkthrough on the REAL UI — but the
actual playthru library needs npm/CDN, which violates the stdlib-only/offline
constraint and would break on judge laptops with blocked CDNs. So: the *concept*
hand-built in ~60 lines of vanilla JS already in the page — a cursor-less
auto-tour that clicks the real buttons and narrates real events. Same story,
zero dependencies.

## Risks

- Narration keyed on events could misfire if the briefing races the script
  (script Mom at 4.0s; briefing paced 1.4s/segment — usually 2-3 segments out).
  Mitigation: beats keyed on events, not timeouts; worst case a beat arrives
  late, never a wrong beat.
- Touching host.py minimally (none planned — narration is pure client-side).
- 35 simulator tests must stay green (no server logic change).
