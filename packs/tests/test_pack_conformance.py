"""Pack conformance: every shipped pack validates; every broken pack screams.

A pack that fails silently is a privacy hole wearing a config file. These tests
pin the loudness: each mutation below MUST raise PackError.
"""

import os
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from packs.loader import load_pack
from packs.schema import validate_pack
from packs.yaml_subset import PackError, parse

PACKS_ROOT = os.path.join(os.path.dirname(__file__), "..")


class ParserTest(unittest.TestCase):
    def test_basic_mapping_and_sequence(self):
        doc = parse("a: 1\nb:\n  - x\n  - y\nc: 'hi # there' # comment\n", path="t")
        self.assertEqual(doc, {"a": 1, "b": ["x", "y"], "c": "hi # there"})

    def test_scalars(self):
        doc = parse("i: 42\nf: 0.5\nt: true\ng: false\nn: null\nm: ~\ne: ''\n", path="t")
        self.assertEqual(doc, {"i": 42, "f": 0.5, "t": True, "g": False,
                               "n": None, "m": None, "e": ""})

    def test_inline_mapping_in_sequence(self):
        doc = parse("items:\n  - name: a\n    v: 1\n  - name: b\n    v: 2\n", path="t")
        self.assertEqual(doc, {"items": [{"name": "a", "v": 1}, {"name": "b", "v": 2}]})

    def test_nested_mapping(self):
        doc = parse("a:\n  b:\n    c: deep\n", path="t")
        self.assertEqual(doc, {"a": {"b": {"c": "deep"}}})

    def test_duplicate_key_fails(self):
        with self.assertRaises(PackError):
            parse("a: 1\na: 2\n", path="t")

    def test_tabs_fail(self):
        with self.assertRaises(PackError):
            parse("a:\n\tb: 1\n", path="t")

    def test_bad_indent_fails(self):
        with self.assertRaises(PackError):
            parse("a:\n   b: 1\n", path="t")  # 3 spaces

    def test_flow_collections_fail(self):
        with self.assertRaises(PackError):
            parse("a: [1, 2]\n", path="t")

    def test_block_scalar_fails(self):
        with self.assertRaises(PackError):
            parse("a: |\n  text\n", path="t")

    def test_comment_inside_quotes_kept(self):
        doc = parse('a: "x # y"\n', path="t")
        self.assertEqual(doc, {"a": "x # y"})

    def test_error_carries_location(self):
        try:
            parse("a:\n   b: 1\n", path="packs/base/roles.yaml")
        except PackError as exc:
            self.assertIn("packs/base/roles.yaml", str(exc))
            self.assertIn(":2:", str(exc))
        else:
            self.fail("expected PackError")


class ShippedPacksValidateTest(unittest.TestCase):
    def test_base_validates(self):
        manifest = validate_pack(os.path.join(PACKS_ROOT, "base"))
        self.assertEqual(manifest["name"], "base")

    def test_en_validates(self):
        manifest = validate_pack(os.path.join(PACKS_ROOT, "en"))
        self.assertEqual(manifest["name"], "en")

    def test_hi_validates(self):
        manifest = validate_pack(os.path.join(PACKS_ROOT, "hi"))
        self.assertEqual(manifest["name"], "hi")

    def test_en_loads(self):
        pack = load_pack(PACKS_ROOT, "en")
        self.assertIn("health.reproductive", pack.taxonomy)
        self.assertAlmostEqual(pack.taxonomy["health.reproductive"]["sensitivity"], 0.95)
        self.assertEqual(pack.roles["child"]["default_clearance"], 1)
        self.assertEqual(pack.roles["unknown"]["default_clearance"], 0)
        self.assertIn("pregnancy", pack.lexicon["health.reproductive"]["terms"])

    def test_hi_loads(self):
        pack = load_pack(PACKS_ROOT, "hi")
        self.assertIn("गर्भवती", pack.lexicon["health.reproductive"]["terms"])
        self.assertIn("garbh", pack.lexicon["health.reproductive"]["terms"])
        # Same taxonomy as en — the language pack does not redefine the world.
        en = load_pack(PACKS_ROOT, "en")
        self.assertEqual(pack.taxonomy, en.taxonomy)
        self.assertEqual(pack.roles, en.roles)

    def test_taxonomy_flattened_paths(self):
        pack = load_pack(PACKS_ROOT, "en")
        for dotted in ("health", "health.reproductive", "health.general", "finance",
                       "gift", "work", "relationship", "legal", "kids"):
            self.assertIn(dotted, pack.taxonomy)


class BrokenPackFailsLoudlyTest(unittest.TestCase):
    """Each mutation must raise PackError. A silent pass here is a test failure."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="packtest-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # A packs root with the REAL base, so load_pack() exercises the full
        # merge + content-validation path for broken language packs.
        shutil.copytree(os.path.join(PACKS_ROOT, "base"),
                        os.path.join(self.tmp, "base"))

    def _write_pack(self, name, files, manifest_extra=""):
        d = os.path.join(self.tmp, name)
        os.makedirs(d)
        manifest = f"name: {name}\nversion: 1\ninherits: base\ndescription: test\n{manifest_extra}"
        with open(os.path.join(d, "pack.yaml"), "w") as fh:
            fh.write(manifest)
        for fname, content in files.items():
            with open(os.path.join(d, fname), "w") as fh:
                fh.write(content)
        # lang packs need the real base for load_pack; validate_pack is enough here.
        return d

    def _good_lang_files(self):
        return {
            "lexicon.yaml": "lexicon:\n  health:\n    terms:\n      - x\n",
            "renditions.yaml": "renditions:\n  event:\n    d4: a\n    d3: b\n    d2: c\n    d1: d\n",
        }

    def test_missing_file_fails(self):
        d = self._write_pack("xx", {"lexicon.yaml": "lexicon:\n  health:\n    terms:\n      - x\n"})
        with self.assertRaises(PackError):
            validate_pack(d)

    def test_unknown_manifest_key_fails(self):
        d = self._write_pack("xx", self._good_lang_files(), manifest_extra="bogus: 1\n")
        with self.assertRaises(PackError):
            validate_pack(d)

    def test_manifest_name_mismatch_fails(self):
        d = os.path.join(self.tmp, "xx")
        os.makedirs(d)
        with open(os.path.join(d, "pack.yaml"), "w") as fh:
            fh.write("name: yy\nversion: 1\ninherits: base\ndescription: test\n")
        with self.assertRaises(PackError):
            validate_pack(d)

    def test_lang_pack_redefining_taxonomy_fails(self):
        files = self._good_lang_files()
        files["taxonomy.yaml"] = "topics:\n  health:\n    sensitivity: 0.1\n"
        d = self._write_pack("xx", files)
        with self.assertRaises(PackError):
            validate_pack(d)

    def test_bad_clearance_fails(self):
        pack = load_pack(PACKS_ROOT, "en")
        self.assertEqual(pack.roles["partner"]["default_clearance"], 4)
        # Mutate a temp copy of base roles: clearance 9 is outside 0..4.
        base = os.path.join(self.tmp, "base")
        with open(os.path.join(base, "roles.yaml"), "w") as fh:
            fh.write("roles:\n  child:\n    default_clearance: 9\n  guest:\n"
                     "    default_clearance: 1\n  elder:\n    default_clearance: 2\n"
                     "  partner:\n    default_clearance: 4\n  unknown:\n"
                     "    default_clearance: 0\n")
        with self.assertRaises(PackError):
            validate_pack(base)

    def test_empty_terms_fail(self):
        files = self._good_lang_files()
        files["lexicon.yaml"] = "lexicon:\n  health:\n    terms: []\n"
        self._write_pack("xx", files)
        with self.assertRaises(PackError):
            load_pack(self.tmp, "xx")

    def test_unknown_placeholder_fails(self):
        files = self._good_lang_files()
        files["renditions.yaml"] = "renditions:\n  event:\n    d4: '{bogus}'\n    d3: b\n    d2: c\n    d1: d\n"
        self._write_pack("xx", files)
        with self.assertRaises(PackError):
            load_pack(self.tmp, "xx")

    def test_lexicon_unknown_topic_fails(self):
        files = self._good_lang_files()
        files["lexicon.yaml"] = "lexicon:\n  mind_reading:\n    terms:\n      - x\n"
        self._write_pack("xx", files)
        with self.assertRaises(PackError):
            load_pack(self.tmp, "xx")

    def test_unknown_role_fails(self):
        base = os.path.join(self.tmp, "base")
        with open(os.path.join(base, "roles.yaml"), "w") as fh:
            fh.write("roles:\n  child:\n    default_clearance: 1\n  guest:\n"
                     "    default_clearance: 1\n  elder:\n    default_clearance: 2\n"
                     "  partner:\n    default_clearance: 4\n  unknown:\n"
                     "    default_clearance: 0\n  overlord:\n    default_clearance: 4\n")
        with self.assertRaises(PackError):
            validate_pack(base)

    def test_sensitivity_out_of_range_fails(self):
        base = os.path.join(self.tmp, "base")
        with open(os.path.join(base, "taxonomy.yaml"), "w") as fh:
            fh.write("topics:\n  health:\n    sensitivity: 1.5\n")
        with self.assertRaises(PackError):
            validate_pack(base)


if __name__ == "__main__":
    unittest.main()
