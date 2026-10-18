# Household Packs — authoring guide

A Household Pack is **data, not code**. It is everything about a household that
varies by culture and language — topic sensitivities, who counts as family,
how a vague-but-natural sentence sounds in Hindi — stored as plain YAML files
that any human can audit. The sealed-speech engine never branches on language;
it reads the pack once and then works with `(item_id, depth, clearance)` numbers
and rendition strings.

If you can edit a YAML file and run one command, you can author a pack.

## File map

```
packs/
  base/                  language-independent core (exactly one)
    pack.yaml            manifest: name "base", version, inherits null
    taxonomy.yaml        topic tree with sensitivity 0..1 per topic
    roles.yaml           the five roles, default clearance depth 0..4 each
    templates.yaml       fallback "boring" templates per kind × depth
  en/                    English language pack (inherits base)
    pack.yaml            manifest: name "en", inherits "base"
    lexicon.yaml         sensitive terms + aliases per topic (for the verifier)
    renditions.yaml      natural renditions per kind × depth
    ui.yaml              cover suffix + probe response strings
  hi/                    Hindi/Hinglish language pack (same four files)
```

The split is structural, enforced by the schema: a base pack must not contain
language files, and a language pack must not redefine base files. There is no
convention to get wrong — a violation fails loudly at validation time.

## The frozen schema

These domains are frozen. A pack cannot extend them; it can only fill them in.

| Domain | Values |
|---|---|
| Item kinds | `event`, `reminder`, `delivery`, `note`, `message_summary` |
| Roles | `child`, `guest`, `elder`, `partner`, `unknown` (exactly these five) |
| Depths | `d4` full detail → `d3` generalized → `d2` vague → `d1` existence-only (`d0` is absorbed into the constant-shape suffix — never rendered) |
| Placeholders | `{title}` `{time}` `{daypart}` `{location}` `{sender}` `{items}` `{category}` (no others) |
| Topic names | lowercase letters, digits, underscore; dotted paths for children (`health.reproductive`) |
| Sensitivity | 0..1 float — higher means less evidence is needed to assume an unwanted listener |
| Clearance | integer 0..4 |

Unknown keys, unknown placeholders, out-of-range numbers, and empty strings all
fail validation. There are no silent defaults: a missing `d2` for a kind is an
error, not an invitation to guess.

## Authoring a new language pack, step by step

Say you want Marathi (`mr`). You never touch `packs/base/`.

**1. Copy the skeleton.**
```bash
cp -r packs/en packs/mr
```

**2. Edit `packs/mr/pack.yaml`.** Set `name: mr`, keep `inherits: base`, bump
nothing else. The manifest name must equal the directory name.

**3. Write `lexicon.yaml` — the most safety-critical file.** For every topic in
`packs/base/taxonomy.yaml`, list the sensitive terms in your language **plus**
transliterations and common misspellings people actually type. The deterministic
leak verifier matches these case-insensitively after Unicode normalization, so
"Cloudnine", "CLOUDNINE" and "cloudnine" all hit — but it cannot match a word
you never listed. Include the Devanagari terms *and* the Latin-script forms
people use in chat (see the `hi` pack: `तोहफ़ा`, `tohfa`, `gift` all listed).
Aliases cover spelling variants: `ob-gyn` also matches `obgyn`.

**4. Write `renditions.yaml`.** For each kind × depth, write the sentence the
room hears. Two rules, both enforced:
- Every depth must be a strict information subset of the one above it.
  `d4` names the thing; `d3` generalizes it; `d2` is vague; `d1` admits almost
  nothing. Read them top-to-bottom: each line must reveal less than the last.
- Only the seven frozen placeholders. A `{category}` in a d3 template is how
  a sensitive topic once leaked into speech (see below) — the validator will
  reject unknown placeholders, but *allowed* placeholders in the wrong depth
  are a judgment call the verifier double-checks.

**5. Write `ui.yaml`.** Two strings: `cover_suffix` (appended to every spoken
turn, e.g. "The rest of your day is on your phone.") and `probe_response`
(the constant reply to fishing questions). These keep the response *shape*
identical across languages — same information, different words.

**6. Validate.**
```bash
earshot-validate-pack --lang mr
```
Fix every FAIL (each carries file and line). Then validate everything:
```bash
earshot-validate-pack
```

**7. Run the language-blind test.** `packs/tests/test_language_blind.py` proves
the engine makes identical depth decisions in `en` and `hi` for the same
scenario — only the strings differ. Your new pack should satisfy the same
property; if a depth decision changes with language, the pack is encoding logic
that belongs in code, and the test will catch it.

## The leak-verifier story (read this before writing templates)

During development, the pack's own deterministic leak verifier fired **twice**
on pack data — not on engine code, on the YAML files:

1. **The `{category}` leak.** A d3 template read `"{category} at {time}"`. For
   an item whose category was *therapy* — a sensitive topic — the "generalized"
   d3 rendition spoke the sensitive word itself. The depth ladder said d3 was
   safe; the data said otherwise. Fixed in the data: d3 templates may not echo
   raw category values for sensitive topics.
2. **The Latin-only gift regex.** The gift-topic terms only covered Latin script.
   A Hindi speaker's surprise gift, written in Devanagari, sailed past the
   verifier undetected. Fixed in the data: every topic's terms now include
   native-script forms *and* the transliterations people actually type.

The lesson is structural: packs are data, data gets policed, and the policing
happens at authoring time (the validator) *and* at render time (the verifier).
Neither trusts the other.

**What the verifier is not.** It is a lexicon blocklist — a lint, not a
security boundary. A red-team probe (2026-10-18) demonstrated the bypass: a d3
template reading "your weekly head-shrinking session at {time}" (slang for
therapy, absent from the lexicon) validates clean *and* verifies clean, while
the literal "therapy" is caught. Paraphrase, slang, and euphemism beat any
blocklist; semantic detection would need embeddings (not stdlib). Treat pack
authorship as a trust boundary — review third-party packs like code. The
actual security boundary is the MonotoneGate + secrecy edges (code, not pack
data): a paraphrased template can only render what the item's clearance
already permits. See Pack-R1 in `docs/residual-risks.md`.

## What the loader guarantees downstream

`load_pack()` merges base + language into one validated `Pack` and the hot path
never sees a language name again. It sees `(item_id, depth: int,
clearance: int)` and rendition strings. Consequences:

- Adding a language cannot change a disclosure decision — only the words.
- The engine is auditable without reading a single non-English file.
- A broken pack cannot ship: `load_pack` raises `PackError` (with file and
  line) instead of degrading.

## What NOT to do

- **Don't add a sixth role or a new placeholder.** The schema is frozen; extend
  the engine's contracts first, then the packs.
- **Don't put logic in renditions.** No conditionals, no "if the listener is
  mom" — YAML has no `if`, and that is deliberate.
- **Don't ship a pack you haven't validated.** `earshot-validate-pack` is one
  command. There is no excuse.
- **Don't commit broken packs, even as test fixtures.** The broken-pack
  mutations used to prove "every violation fails loudly" run in temp dirs and
  are never checked in. A broken pack in the repo is a loaded footgun.
- **Don't use a YAML library's full feature set.** Pack files are parsed by a
  deliberately dumb subset parser (`packs/yaml_subset.py`): no anchors, no
  flow collections, no block scalars, no tabs. If your editor wants to be
  clever, tell it no.
