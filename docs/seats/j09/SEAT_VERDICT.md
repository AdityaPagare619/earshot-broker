# SEAT_VERDICT — J9: Adjacent-device exec (Fire TV / Ring / wearable)

**Lens:** Impact + Design. **Signature question:** does this generalize, or is it a
one-track hack?

## Verdict on the current state: PROMISING THESIS, ONE-TRACK EVIDENCE

The 57-page dossier is genuinely strong thinking — the sealed-task pivot is the
right restatement (principal-mindset §5: it changes what we *believe*, not just the
number). The kernel is real code with 24 green tests, and labels/leases are a
legitimate generalization substrate. I buy the thesis.

But from my seat, the repo seed is a **one-track hack wearing platform clothes**.
Everything concrete in it is calendar-shaped: the scenarios are appointments, the
blueprint's AST example centers `load_busy_intervals`, and the adapter contract
(§3) exists only as prose. There is no adapter abstraction in code, no second
source, no enforcement of "unsupported sources fail private." If I asked the team
today to add medication reminders, the honest answer would be "fork the calendar
code and hand-edit labels" — and that is exactly how one-track hacks are born.
On a Fire TV or a Ring timeline, where the sources are watch history and motion
clips rather than calendar events, this codebase as it stands generalizes by
copy-paste. Copy-paste is not a platform.

## What's strong (keep)

1. **The kernel is source-agnostic by construction.** `Fact`/`Label`/`Lease` know
   nothing about calendars. That's the right foundation — my adapters plug into
   it without touching it.
2. **§3 names the real contract items** (schemas, owner/subject mapping, field
   labels, transformations, mutation recipients, idempotency, freshness,
   deletion). Prose is not code, but at least the checklist is complete.
3. **"Fail private" is the correct default** for unsupported sources. Asserted,
   not yet enforced — my build enforces it in the registry.

## What's weak (my build must fix)

1. **No adapter abstraction exists.** Worse than missing: the absence means the
   first real adapter (whoever writes it) sets the precedent by hand-wiring.
   Precedent-by-first-implementation is how you get three incompatible adapters.
2. **Field-label defaults are described, not encoded.** Blueprint pipeline B
   step 4 ("set a private default for all imported fields") has no code path.
   A label default that lives in a doc is a label default that gets forgotten.
3. **Mutation recipients and idempotency are prose.** The calendar section says
   "do not overwrite attendees or notification flags during a time-only change"
   — there is no mechanism that prevents it.
4. **Recurrence is a known minefield with no code.** "Expand recurrence for a
   bounded day/time range using a tested library" — but ₹0/std-lib means no
   library; someone must write bounded expansion with tests, or the first
   recurring "therapy every Tuesday" silently becomes one event.
5. **The second source doesn't exist.** The generalization claim is currently
   unfalsifiable. My mandate: make it falsifiable — tasks/reminders through the
   same kernel, same tools, no fork.

## What would fail in my review

- A tasks adapter that subclasses the calendar adapter. (Inheritance across
  domains is the copy-paste hack with better syntax.)
- An adapter that fetches full event details "because the filter happens later."
  Least-privilege ingestion is the security posture; busy-intervals-first is
  named in the blueprint and I will enforce it.
- Any path where an unknown source degrades to "best-effort public." Fail
  private, loudly, with a typed error the gateway must handle — never a silent
  empty result that looks like "no events today."
- Claims about Fire TV / Ring / wearable integration. I will not claim a single
  device integration. What I *will* claim: the adapter contract is device-class
  agnostic, demonstrated by two sources with different schemas, subjects,
  mutation recipients, and freshness models running through one kernel.

## Confidence: 70/100

70 that the adapter-contract approach is the right generalization mechanism
(the dossier's §8.4 argument is sound and the kernel gives me the substrate).
30 points of doubt: whether *I* can make the second adapter genuinely
config-level rather than a polite fork — that is the thing my tests must prove,
especially the test that adds a third source shape without touching adapter
base code. If that test is awkward, the design is wrong and I redesign.

*What was known when: seed commit 7299214, kernel 24/24 green, no adapter code
exists, six principal skills read, dossier §§8.4/9/3 read.*
