# EARSHOT — container image.
#
# Build:  docker build -t earshot .
# Demo:   docker run --rm earshot
#           → runs the 5-beat sealed-speech demo (fixture-based, no network needed).
#
# Server / simulator (need the --host flag — see note below):
#   docker run --rm -p 8000:8000 earshot earshot-server --host 0.0.0.0
#   docker run --rm -p 8734:8734 earshot earshot-sim --host 0.0.0.0
#
# NOTE (honest): as of this writing the MCP gateway and the simulator hard-bind
# to 127.0.0.1 (services/gateway/mcp/server.py, apps/simulator/host.py), so plain
# `-p` port mapping cannot reach them from outside the container until the --host
# flag lands (pro-server lane). The demo CMD below is unaffected and is the
# verified container story. Do not advertise `docker run -p …` for the server
# in the README until --host exists.
#
# VERIFICATION CHECKLIST (not yet done — no Docker daemon on the build machine):
#   [ ] docker build -t earshot .            succeeds
#   [ ] docker run --rm earshot              prints ALL 5 BEATS PASSED, exit 0
#   [ ] docker run --rm earshot python -m pytest   (optional: full suite in-image)

FROM python:3.12-slim

# Least privilege: the package installs as root (needs site-packages write),
# everything runs as the unprivileged `earshot` user.
RUN useradd -m -s /bin/bash earshot

WORKDIR /app

# Copy the repo. .dockerignore keeps .git/, seat dossiers, bytecode and venvs
# out of the build context.
COPY . /app

# stdlib-only project: the only install step is the package itself.
# `--no-cache-dir` keeps the image lean; entry points land in /usr/local/bin.
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir .

# Drop privilege before anything runs.
USER earshot

# The 5-beat sealed-speech demo: fixture-based, non-interactive, no network.
# Exec form (not shell form) so docker stop signals reach the process.
CMD ["earshot-demo"]
