import os
import time

import django
from django.db import connections
from django.db.utils import OperationalError


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    timeout_seconds = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
    interval_seconds = float(os.getenv("DB_WAIT_INTERVAL", "2"))

    django.setup()

    start = time.monotonic()
    while True:
        try:
            connections["default"].cursor().close()
            return 0
        except OperationalError as exc:
            elapsed = time.monotonic() - start
            if elapsed >= timeout_seconds:
                print(f"Database unavailable after {timeout_seconds}s: {exc}")
                return 1
            time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
