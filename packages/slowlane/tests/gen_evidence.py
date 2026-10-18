"""Generate evidence/slowlane/run-summary.txt — measured claims, not prose."""
import io
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

loader = unittest.TestLoader()
suite = loader.discover(os.path.join(REPO, "packages", "slowlane", "tests"),
                        top_level_dir=REPO)
stream = io.StringIO()
runner = unittest.TextTestRunner(stream=stream, verbosity=1)
result = runner.run(suite)

out_dir = os.path.join(REPO, "evidence", "slowlane")
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "run-summary.txt"), "w") as f:
    f.write("S1 slowlane test evidence\n")
    f.write("=========================\n")
    f.write(f"tests run: {result.testsRun}\n")
    f.write(f"failures: {len(result.failures)}\n")
    f.write(f"errors: {len(result.errors)}\n")
    f.write(f"verdict: {'GREEN' if result.wasSuccessful() else 'RED'}\n")
    f.write("\n--- unittest output ---\n")
    f.write(stream.getvalue())

# Canonical counterfactual artifact: the two projection byte-strings.
from earshot.slowlane import compiler, quarantine, seam  # noqa: E402
from test_counterfactual import _projection  # noqa: E402

store_a, comp_a = quarantine.QuarantineStore(), compiler.TableCompiler()
store_b, comp_b = quarantine.QuarantineStore(), compiler.TableCompiler()
proj_a = _projection(store_a, comp_a, with_email=False)
proj_b = _projection(store_b, comp_b, with_email=True)
with open(os.path.join(out_dir, "counterfactual-projections.txt"), "w") as f:
    f.write("world A (no email) projection bytes:\n")
    f.write(proj_a.decode() + "\n\n")
    f.write("world B (adversarial email, QUARANTINED) projection bytes:\n")
    f.write(proj_b.decode() + "\n\n")
    f.write(f"byte-identical: {proj_a == proj_b}\n")
    f.write(f"projection non-empty (not vacuous): {len(proj_a) > 0}\n")

print(f"tests={result.testsRun} failures={len(result.failures)} "
      f"errors={len(result.errors)} counterfactual_identical={proj_a == proj_b}")
