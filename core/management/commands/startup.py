"""
Single-process startup command that replaces the multi-step entrypoint.

Runs all pre-flight steps inside one Django process so the ~45s boot tax
is paid exactly once instead of once per step.
"""
import os
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Run all startup steps (db wait, migrate, storage bootstrap, theme reconcile, collectstatic) in one process."

    def add_arguments(self, parser):
        parser.add_argument("--no-migrate", action="store_true")
        parser.add_argument("--no-bootstrap-storage", action="store_true")
        parser.add_argument("--no-theme-reconcile", action="store_true")
        parser.add_argument("--no-collectstatic", action="store_true")
        parser.add_argument("--no-db-wait", action="store_true")

    def handle(self, *args, **options):
        if not options["no_db_wait"]:
            self._wait_for_db()

        if not options["no_migrate"]:
            self.stdout.write("Running migrations...")
            call_command("migrate", "--noinput", verbosity=1, stdout=self.stdout, stderr=self.stderr)

        if not options["no_bootstrap_storage"]:
            storage_bootstrap = os.getenv("STORAGE_BOOTSTRAP", "true").strip().lower()
            if storage_bootstrap in ("1", "true", "yes", "on"):
                self.stdout.write("Bootstrapping storage...")
                call_command("bootstrap_storage", stdout=self.stdout, stderr=self.stderr)

        if not options["no_theme_reconcile"]:
            theme_reconcile = os.getenv("THEME_RECONCILE", "true").strip().lower()
            if theme_reconcile in ("1", "true", "yes", "on"):
                self.stdout.write("Reconciling themes...")
                call_command("theme_reconcile", stdout=self.stdout, stderr=self.stderr)

        if not options["no_collectstatic"]:
            collectstatic = os.getenv("COLLECTSTATIC", "true").strip().lower()
            if collectstatic in ("1", "true", "yes", "on"):
                self.stdout.write("Collecting static files...")
                call_command("collectstatic", "--noinput", verbosity=1, stdout=self.stdout, stderr=self.stderr)

        self.stdout.write(self.style.SUCCESS("Startup complete."))

    def _wait_for_db(self):
        timeout = int(os.getenv("DB_WAIT_TIMEOUT", "60"))
        interval = float(os.getenv("DB_WAIT_INTERVAL", "2"))
        self.stdout.write("Waiting for database...")
        start = time.monotonic()
        while True:
            try:
                connections["default"].cursor().close()
                return
            except OperationalError as exc:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    raise SystemExit(f"Database unavailable after {timeout}s: {exc}")
                time.sleep(interval)
