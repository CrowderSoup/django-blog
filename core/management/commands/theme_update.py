from django.core.management.base import BaseCommand, CommandError

from core.models import ThemeInstall
from core.themes import ThemeUploadError, update_theme_from_git


class Command(BaseCommand):
    help = "Update a git-installed theme and sync it to storage."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="Theme slug to update.")
        parser.add_argument("--ref", default=None, help="Optional git ref to checkout.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and show what would change without updating.",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        ref = options["ref"]
        dry_run = options["dry_run"]

        try:
            install = ThemeInstall.objects.get(slug=slug)
        except ThemeInstall.DoesNotExist as exc:
            raise CommandError(f"Theme install '{slug}' not found.") from exc

        if install.source_type != ThemeInstall.SOURCE_GIT:
            raise CommandError(f"Theme '{slug}' is not installed from git.")

        try:
            result = update_theme_from_git(install, ref=ref, dry_run=dry_run)
        except ThemeUploadError as exc:
            raise CommandError(str(exc)) from exc

        prefix = "DRY RUN:" if dry_run else "Updated:"
        if not result.updated:
            prefix = "DRY RUN:" if dry_run else "No changes:"
        message = f"{prefix} {slug} ref={result.ref or '-'} commit={result.commit or '-'}"
        self.stdout.write(self.style.SUCCESS(message))
