import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.models import ThemeInstall


class Command(BaseCommand):
    help = "List installed themes and their source metadata."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Limit output to a single theme slug.")
        parser.add_argument("--json", action="store_true", help="Emit JSON output.")

    def handle(self, *args, **options):
        slug = options.get("slug")
        as_json = options.get("json", False)

        installs = ThemeInstall.objects.all()
        if slug:
            if not installs.filter(slug=slug).exists():
                raise CommandError(f"No installed theme found for slug '{slug}'.")
            installs = installs.filter(slug=slug)

        rows = [self._serialize_install(install) for install in installs.order_by("slug")]

        if as_json:
            self.stdout.write(json.dumps(rows))
            return

        if not rows:
            self.stdout.write("No installed themes found.")
            return

        headers = [
            "SLUG",
            "SOURCE",
            "REF",
            "URL",
            "STATUS",
            "LAST_SYNCED_AT",
        ]
        widths = {header: len(header) for header in headers}
        for row in rows:
            widths["SLUG"] = max(widths["SLUG"], len(row["slug"]))
            widths["SOURCE"] = max(widths["SOURCE"], len(row["source_type"]))
            widths["REF"] = max(widths["REF"], len(row["source_ref"]))
            widths["URL"] = max(widths["URL"], len(row["source_url"]))
            widths["STATUS"] = max(widths["STATUS"], len(row["last_sync_status"]))
            widths["LAST_SYNCED_AT"] = max(widths["LAST_SYNCED_AT"], len(row["last_synced_at"]))

        format_str = "  ".join(f"{{{header}:<{widths[header]}}}" for header in headers)
        self.stdout.write(format_str.format(**{header: header for header in headers}))
        for row in rows:
            self.stdout.write(
                format_str.format(
                    SLUG=row["slug"],
                    SOURCE=row["source_type"],
                    REF=row["source_ref"],
                    URL=row["source_url"],
                    STATUS=row["last_sync_status"],
                    LAST_SYNCED_AT=row["last_synced_at"],
                )
            )

    def _serialize_install(self, install: ThemeInstall) -> dict[str, Any]:
        last_synced_at = install.last_synced_at.isoformat() if install.last_synced_at else ""
        return {
            "slug": install.slug,
            "source_type": install.source_type,
            "source_ref": install.source_ref or "",
            "source_url": install.safe_source_url() or "",
            "last_sync_status": install.last_sync_status or "",
            "last_synced_at": last_synced_at,
            "version": install.version or "",
        }
