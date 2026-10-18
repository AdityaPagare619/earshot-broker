# run from repo root
PYTHONPATH=packages/kernel python3 -m unittest discover -s tests
# (failure_paths suite needs its harness dir on the path)
PYTHONPATH=packages/kernel:tests/failure_paths python3 -m unittest discover -s tests/failure_paths
