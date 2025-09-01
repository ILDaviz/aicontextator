# src/scripts.py

import subprocess
import sys


def _run_command(command):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        sys.exit(1)


def format():
    _run_command(["ruff", "format", "."])


def lint():
    _run_command(["ruff", "check", "."])


def test():
    _run_command(["pytest"])
