from __future__ import annotations

import argparse
import logging

from .config import Settings
from .scheduler import run_once, serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Bikash AI durable reminder worker")
    parser.add_argument("--once", action="store_true", help="process at most one due reminder")
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    if args.once:
        run_once(settings.database_path)
    else:
        serve(settings.database_path, max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
