"""Shim: run the personal quickstart.

Prefer the entry point: `earshot personal-quickstart` (after `pip install -e .`).
This shim also works from a bare clone with no install: it maps the
package-dir layout (see pyproject.toml [tool.setuptools.package-dir]) onto
the `earshot` package __path__ and retries before giving up.
"""
import sys
from pathlib import Path


def _bootstrap_no_install():
    HERE = Path(__file__).resolve().parent
    REPO_ROOT = HERE.parent.parent
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import earshot  # noqa: E402  (resolves to src/earshot)

    # Submodule search dirs: each must CONTAIN the submodule dir/file.
    for rel in ("apps/personal", "packages/kernel"):
        p = str(REPO_ROOT / rel)
        if p not in earshot.__path__:
            earshot.__path__.append(p)
    kernel_dir = str(REPO_ROOT / "packages" / "kernel")
    if kernel_dir not in sys.path:
        sys.path.insert(0, kernel_dir)


try:
    from earshot.personal.quickstart import main
except ImportError:
    _bootstrap_no_install()
    try:
        from earshot.personal.quickstart import main
    except ImportError:
        sys.exit("earshot is not installed. From the repo root, run: pip install -e .")

if __name__ == "__main__":
    sys.exit(main())
