"""Repo-wide pytest configuration."""

import os

# Python 3.14+ argparse colorizes usage/help output; CI sets
# FORCE_COLOR=1, which would inject ANSI escapes into captured output
# and break substring assertions on help text. PYTHON_COLORS takes
# precedence over FORCE_COLOR/NO_COLOR, pinning plain output
# deterministically for every Python version and environment.
os.environ["PYTHON_COLORS"] = "0"
