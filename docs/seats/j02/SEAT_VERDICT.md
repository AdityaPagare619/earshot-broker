# SEAT VERDICT — J2 · Chief Evangelist, Alexa
Lens: Idea + Tech Implementation. Signature question: "Does it feel like it comes through an Echo? Is it obvious?"

## Verdict: the idea survives my review; the demo does not exist yet, and that is the whole game.

### What's strong (keep, protect)
1. **The sealed-task pivot is the right product call.** The old answer-filter promised
   an interception boundary an MCP add-on cannot own (§1.1). A chief evangelist
   cannot demo a lie — the new honesty ("we do not claim to intercept all Alexa
   output") is the reason a judge will trust the rest. This is the single biggest
   idea-strength on the table.
2. **The walk-in beat is the evangelist moment.** "The assistant keeps helping when
   the room stops being private" is visceral, 10-second-legible, and impossible
   with a mute button. If it works live, it carries Idea points by itself.
3. **Protocol rigor is real.** Pinned 2025-11-25, Streamable HTTP, the 24-test
   kernel, label propagation with control-flow taint (§6.3/§4 blueprint) — this is
   not a chatbot with a redaction regex. Tech Implementation points are earnable.

### What's weak (brutal)
1. **`apps/simulator/` is an empty directory.** The controlled host — the entire
   Profile B demo surface, the walk-in beat, the thing every judge watches — does
   not exist. From my seat this is the #1 risk in the whole program: the climax
   of the video is currently a story in a PDF.
2. **The kernel's prepare/redeem has no serialization boundary.** Blueprint §6
   demands prepare/commit/audience_changed ordering with a lock; the kernel even
   admits "a distributed renderer needs atomic ordering." If my arbiter doesn't
   implement the epoch-advance-vs-commit race correctly, the walk-in demo is
   theater: a late segment could play after Mom enters, and no test would catch it.
   J10 will find this. J4 will fail it.
3. **Nothing about the current repo "feels like an Echo."** A dev dashboard with
   buttons does not pass my signature question. Voice-first cadence, the light
   ring, spoken delivery in small segments, a discreet room strip — none of it
   exists. If the simulator looks like a SOC console, the idea reads as
   infrastructure, not as Alexa.
4. **"Is it obvious?" — not yet.** `prepare_day_brief` / `resolve_day_change` /
   `continue_on_personal_device` / `withdraw_request` are not obvious to a
   first-time viewer. The 10-second legibility test is: "Alexa plans your day
   without telling the room why." My UI must make the private/public boundary
   VISIBLE — speaker and phone side by side — or the idea needs a paragraph, and
   paragraphs lose.
5. **The strict-existence fixture kills my best beat and I must respect it.**
   The old phone buzz was great evangelism and the dossier correctly forbids it
   in strict mode (a buzz leaks existence). My simulator must implement BOTH the
   quiet path (strict: inbox syncs silently, no count, no sound) and the nudge
   path (relaxed), and make the difference legible — otherwise the demo teaches
   the wrong lesson.
6. **Latency is currently a kernel number, not a product number.** The 500ms
   QuickStart budget applies to the whole client-visible MCP round trip (§13.1).
   My simulator must measure and display actual round-trip times. A fast kernel
   does not compensate for a slow host.

### What would fail in my review (red lines)
- A "Mom enters" button that just swaps text on screen. The audience event must
  travel the real path: event → stop output FIRST → epoch++ → invalidate grants
  → keep task state. Anything less is a mockup with extra steps.
- No visible Profile A vs Profile B distinction. The simulator IS Profile B and
  must say so on screen, permanently: "independent simulator — not a live
  Alexa+ device."
- Any claim that the walk-in "stops Alexa." It stops OUR renderer. The label
  must say exactly that.
- Speech synthesis presented as the safety mechanism. Browser TTS is
  presentation (§11.3: not a hard real-time cutoff); the arbiter's segment gate
  is the enforcement. Confuse the two and I kill the demo.

### What I'm building (my mandate, my bar)
`apps/simulator/`: a real MCP client (stdlib, pinned 2025-11-25), a local output
arbiter implementing blueprint §6 ordering with the epoch race closed, an
audience event source (manual + scripted, labeled simulated), and an Echo-class
web host where the walk-in path runs for real against the kernel — with the MCP
client path tested against a protocol-conformance harness and one env var away
from J3's server. It will feel like an Echo, read in 10 seconds, and label every
honest boundary on screen.

**My evangelist promise:** a judge will watch the walk-in beat and say "that's
Alexa, but smarter" — and everything they saw will be true.
