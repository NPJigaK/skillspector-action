from __future__ import annotations

import sys

from .config import Config
from .runner import run_action


def main() -> int:
    return run_action(Config.from_env())


if __name__ == "__main__":
    sys.exit(main())
