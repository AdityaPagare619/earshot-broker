# run from repo root
PYTHONPATH=packages/kernel python3 -m unittest discover -s tests
PYTHONPATH=packages/kernel python3 -m unittest discover -s packages/kernel
