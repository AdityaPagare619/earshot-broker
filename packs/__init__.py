"""The Household Pack is data. This package parses and validates it.

 packs/base/   language-independent core (taxonomy, roles, fallback templates)
 packs/en/     English lexicon + renditions
 packs/hi/     Hindi (Devanagari) + Hinglish lexicon + renditions

yaml_subset.py  the deliberately-dumb parser (mappings, sequences, scalars only)
schema.py       the frozen schema — violations fail loudly, never silently
loader.py       base + language overlay -> one validated Pack object
"""
