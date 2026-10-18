# pro-docker — DESIGN.md

**Lane:** Dockerfile + .dockerignore for the professional public repo.
**Base:** main @ c422bae (packaging, unified pytest, Windows pass, CI merged).
**Date:** 2026-10-18.

## 1. What the image is for

A judge (or any developer) with Docker but no Python setup should be able to run:

```bash
docker build -t earshot .
docker run --rm earshot          # the 5-beat sealed-speech demo, exit 0
```

That is the whole promise. The demo is fixture-based (`[SIMULATOR][FIXTURE]`),
non-interactive, stdlib-only — it needs no network, no credentials, no volume mounts.
It is the ideal container workload.

## 2. Image design

| Decision | Choice | Why |
|---|---|---|
| Base | `python:3.12-slim` | Matches `requires-python >=3.10`; slim keeps it small; 3.12 is the newest version CI tests |
| Dependencies | **none** (stdlib only) | The repo's zero-dependency rule is a feature — the image has no pip-install step beyond the package itself, so builds are fast and reproducible |
| Install | `pip install .` (as root, into site-packages) | Works with the setuptools `package-dir` mapping; entry points land in `/usr/local/bin` |
| Runtime user | non-root `earshot` | Least privilege; the installed package and entry points are world-readable/executable |
| Default CMD | `["earshot-demo"]` (exec form) | Exec form → SIGTERM/SIGINT reach the Python process directly, no `sh` in between |
| WORKDIR | `/app` | Conventional, keeps the build context path stable |
| Healthcheck | none | The default CMD is a batch demo, not a long-running service — a healthcheck would be theater |

Deliberately NOT included: multi-stage builds (nothing to compile — pure Python +
YAML data, a second stage would add lines for zero bytes saved), a virtualenv inside
the image (the container IS the isolation), pinned pip (stdlib-only means the
dependency graph is empty; pinning would be theater).

## 3. The honest limitation: server / simulator port mapping

**Finding (P0 for the docker-server story):** both long-running servers hard-bind
to `127.0.0.1`:

- `services/gateway/mcp/server.py:442` — `ThreadedMCPServer(("127.0.0.1", port), …)`
- `apps/simulator/host.py:460` — `ThreadingHTTPServer(("127.0.0.1", args.port), …)`

Inside a container, `127.0.0.1` is the *container's* loopback. `docker run -p 8000:8000`
forwards host traffic to the container's external interface — a process listening
only on container-loopback never receives it. **Port mapping does not work today.**

This is not fixable inside my lane: the bind address lives in `server.py` / `host.py`,
which are owned by the pro-server / pro-sim lanes (concurrent work — editing them
here would cause merge conflicts). The correct fix is the `--host` flag the
pro-server lane was tasked with ("graceful shutdown, --host flag, structured
logging"). Workarounds I considered and rejected:

- `docker run --network host` — works on Linux, silently broken on Docker Desktop
  (Mac/Windows, where most judges live). Documenting it as *the* path would be dishonest.
- A stdlib TCP forwarder inside the image (0.0.0.0 → 127.0.0.1) — a moving part that
  adds latency and failure modes to work around a one-line fix in the server. Rejected.

**What ships in this lane:**
- `CMD ["earshot-demo"]` — the story that is real today.
- Dockerfile comments + this DESIGN.md document the exact server/sim commands that
  become correct once `--host` lands: `docker run --rm -p 8000:8000 earshot earshot-server --host 0.0.0.0`
  and `docker run --rm -p 8734:8734 earshot earshot-sim --host 0.0.0.0` (host.py has no
  --host flag yet either — same coordination note).
- **Coordination note for Petu:** merge pro-docker together with pro-server; until
  `--host` exists, do not advertise `docker run -p …` for the server/sim in the README.

## 4. .dockerignore

Excluded from the build context (smaller context, faster builds, no secrets risk):

```
.git/                # history never belongs in an image
__pycache__/  *.pyc  # bytecode regenerates
.pytest_cache/       # test artifacts
.venv/  venv/        # local virtualenvs
*.egg-info/          # build artifacts
docs/seats/          # internal build logs (16 seat dossiers — private archive)
docs/dossier/        # the 57-page dossier (private archive)
node_modules/        # not used, but cheap insurance
.DS_Store
```

NOT excluded: `docs/` (minus the above), `evidence/`, `tests/` — they are small and
a judge may want `docker run --rm earshot python -m pytest` to work inside the image.
Verified: no runtime code path reads `docs/` or `evidence/` (grep over demo/,
server.py, host.py, src/earshot/ — zero hits), so the exclusions cannot break the demo.

## 5. Verification boundary (honest)

**Docker is not installed on this machine and cannot be installed here** (no daemon,
no privileges). Therefore:

- The Dockerfile was NOT built or run. Every line was reviewed by hand against the
  actual repo state (entry-point names from `pyproject.toml [project.scripts]`,
  base-image tag exists on Docker Hub as `python:3.12-slim`, `useradd` flags valid
  on Debian slim, `pip install .` validated logically against the setuptools mapping).
- CI does not build the image either (no Docker in the test matrix — pro-ci lane).
- **Before the public repo goes live, someone must run `docker build -t earshot .`
  and `docker run --rm earshot` on a real Docker host** and paste the output. I have
  left that as an explicit checklist item in the Dockerfile header comment rather
  than claiming it works.

## 6. kemiljk critic pass (self-review)

Applied the skill's "draft → critique → revise" loop to the Dockerfile (adapted from
UI to infrastructure — the failure mode is the same: shipping the median):

1. **Median failure: `CMD earshot-demo` (shell form).** Shell form wraps the process
   in `sh -c`, which swallows SIGTERM — `docker stop` would hang for 10s then SIGKILL.
   → Fixed: exec form `CMD ["earshot-demo"]`.
2. **Median failure: running as root.** Most generated Dockerfiles never add a user.
   → Fixed: `useradd -m earshot` + `USER earshot` before CMD. Install stays as root
   (needs write to site-packages), runtime drops privilege.
3. **Median failure: no .dockerignore.** The build context would ship `.git/` (full
   history, including the private-archive-bound seat dossiers) into the daemon.
   → Fixed: .dockerignore excludes `.git/`, seat dossiers, bytecode, venvs.
4. **Median failure: documenting `docker run -p` for the server without checking the
   bind address.** The polished-looking README line would silently not work.
   → Fixed: documented the 127.0.0.1 finding honestly (§3), no fake port-mapping docs.
5. **Leftover default check:** `WORKDIR /app` — deliberate (stable COPY target).
   `pip install .` over `pip install -e .` — deliberate (images are immutable; editable
   installs in images are a bug). No HEALTHCHECK — deliberate (batch CMD, §2).
