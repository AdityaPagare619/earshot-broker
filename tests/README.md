# run from repo root
PYTHONPATH=packages/kernel python3 -m unittest discover -s tests
# (failure_paths suite needs its harness dir on the path)
PYTHONPATH=packages/kernel:tests/failure_paths python3 -m unittest discover -s tests/failure_paths

# Windows (PowerShell): PYTHONPATH entries are separated with `;`, and the
# variable is set per-command with $env:. The two invocations above become:
#   $env:PYTHONPATH = "packages/kernel"; python -m unittest discover -s tests
#   $env:PYTHONPATH = "packages/kernel;tests/failure_paths"; python -m unittest discover -s tests/failure_paths
# (cmd.exe: `set PYTHONPATH=packages/kernel;tests/failure_paths && python -m unittest discover -s tests/failure_paths`)
