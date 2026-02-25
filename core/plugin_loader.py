from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from django.utils import timezone

logger = logging.getLogger(__name__)

PLUGIN_META_FILENAME = "plugin.json"
PLUGINS_DIRNAME = "plugins"
_DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent


class PluginInstallError(Exception):
    """Raised when a plugin cannot be installed or updated."""


@dataclass
class PluginDefinition:
    name: str
    path: Path
    label: str
    version: str = ""
    description: str = ""
    author: str = ""
    django_app: str = ""


def get_plugins_root(base_dir: Optional[Path] = None) -> Path:
    if base_dir is not None:
        return Path(base_dir)

    try:
        from django.conf import settings

        configured_root = getattr(settings, "PLUGINS_ROOT", None)
        if configured_root:
            return Path(configured_root)
        return Path(getattr(settings, "BASE_DIR")) / PLUGINS_DIRNAME
    except Exception:
        return _DEFAULT_BASE_DIR / PLUGINS_DIRNAME


def discover_plugins(base_dir: Optional[Path] = None) -> list[PluginDefinition]:
    """Scan PLUGINS_ROOT for plugin.json files and return discovered plugins."""
    plugins_root = get_plugins_root(base_dir)
    if not plugins_root.exists():
        return []

    plugins: list[PluginDefinition] = []
    for plugin_dir in plugins_root.iterdir():
        if not plugin_dir.is_dir():
            continue

        meta_path = plugin_dir / PLUGIN_META_FILENAME
        if not meta_path.exists():
            continue

        try:
            metadata = json.loads(meta_path.read_text())
        except Exception as exc:
            logger.warning("Could not parse plugin.json in %s: %s", plugin_dir, exc)
            continue

        name = metadata.get("name") or plugin_dir.name
        label = metadata.get("label") or name.replace("-", " ").title()
        plugins.append(
            PluginDefinition(
                name=name,
                path=plugin_dir,
                label=label,
                version=metadata.get("version", ""),
                description=metadata.get("description", ""),
                author=metadata.get("author", ""),
                django_app=metadata.get("django_app", ""),
            )
        )

    plugins.sort(key=lambda p: p.label.lower())
    return plugins


def get_plugin_definition(name: str, base_dir: Optional[Path] = None) -> Optional[PluginDefinition]:
    for plugin in discover_plugins(base_dir=base_dir):
        if plugin.name == name:
            return plugin
    return None


def _is_public_git_url(url: str) -> bool:
    parsed = urlsplit(url)
    if not parsed.scheme:
        if url.startswith(("/", "./", "../")):
            return True
        return "@" not in url
    if parsed.scheme in ("http", "https"):
        return parsed.username is None and parsed.password is None and "@" not in parsed.netloc
    if parsed.scheme == "file":
        return True
    return False


def _ensure_git_url_allowed(url: str) -> None:
    try:
        from django.conf import settings

        allow_private = getattr(settings, "PLUGIN_GIT_ALLOW_PRIVATE", False)
    except Exception:
        allow_private = False

    if allow_private:
        return

    if not _is_public_git_url(url):
        raise PluginInstallError(
            "Private git URLs are disabled. Set PLUGIN_GIT_ALLOW_PRIVATE to enable them."
        )


def _run_git(command: list[str], *, error_message: str) -> None:
    if shutil.which(command[0]) is None:
        raise PluginInstallError(
            "Git is required to install plugins from git. Ensure the 'git' executable is available in PATH."
        )
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PluginInstallError(
            "Git is required to install plugins from git. Ensure the 'git' executable is available in PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            raise PluginInstallError(f"{error_message}: {detail}") from exc
        raise PluginInstallError(error_message) from exc


def _run_git_capture(command: list[str], *, error_message: str) -> str:
    if shutil.which(command[0]) is None:
        raise PluginInstallError(
            "Git is required to install plugins from git. Ensure the 'git' executable is available in PATH."
        )
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PluginInstallError(
            "Git is required to install plugins from git. Ensure the 'git' executable is available in PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            raise PluginInstallError(f"{error_message}: {detail}") from exc
        raise PluginInstallError(error_message) from exc
    return result.stdout.strip()


def _write_installed_plugins_file(django_apps: list[str]) -> None:
    """Rewrite config/installed_plugins.py with the current list of plugin app names."""
    try:
        from django.conf import settings
        base_dir = Path(settings.BASE_DIR)
    except Exception:
        base_dir = _DEFAULT_BASE_DIR

    installed_plugins_path = base_dir / "config" / "installed_plugins.py"
    lines = ["# Auto-generated by webstead plugin manager. Do not edit manually.\n"]
    lines.append("INSTALLED_PLUGIN_APPS = [\n")
    for app in django_apps:
        lines.append(f'    "{app}",\n')
    lines.append("]\n")
    installed_plugins_path.write_text("".join(lines))


def _get_installed_plugin_apps() -> list[str]:
    """Return the current list of installed plugin app names."""
    try:
        from config.installed_plugins import INSTALLED_PLUGIN_APPS
        return list(INSTALLED_PLUGIN_APPS)
    except ImportError:
        return []


def _touch_wsgi() -> None:
    """Touch wsgi.py to trigger server reload."""
    try:
        from django.conf import settings
        base_dir = Path(settings.BASE_DIR)
    except Exception:
        base_dir = _DEFAULT_BASE_DIR

    wsgi_path = base_dir / "config" / "wsgi.py"
    try:
        wsgi_path.touch()
    except Exception as exc:
        logger.warning("Could not touch wsgi.py to trigger reload: %s", exc)


def install_plugin_from_git(
    git_url: str,
    slug: str,
    *,
    ref: str = "",
    base_dir: Optional[Path] = None,
) -> PluginDefinition:
    """Clone a plugin from a git repository and register it."""
    if not git_url:
        raise PluginInstallError("Git URL is required to install a plugin.")
    if not slug:
        raise PluginInstallError("Plugin slug is required.")

    _ensure_git_url_allowed(git_url)

    plugins_root = get_plugins_root(base_dir)
    plugins_root.mkdir(parents=True, exist_ok=True)
    install_dir = plugins_root / slug

    if install_dir.exists():
        shutil.rmtree(install_dir)

    _run_git(
        ["git", "clone", "--depth", "1", git_url, str(install_dir)],
        error_message="Unable to clone plugin repository",
    )
    if ref:
        _run_git(
            ["git", "-C", str(install_dir), "fetch", "--depth", "1", "origin", ref],
            error_message=f"Unable to fetch ref '{ref}'",
        )
        _run_git(
            ["git", "-C", str(install_dir), "checkout", ref],
            error_message=f"Unable to checkout ref '{ref}'",
        )

    commit = _run_git_capture(
        ["git", "-C", str(install_dir), "rev-parse", "HEAD"],
        error_message="Unable to determine plugin commit",
    )

    meta_path = install_dir / PLUGIN_META_FILENAME
    if not meta_path.exists():
        shutil.rmtree(install_dir, ignore_errors=True)
        raise PluginInstallError(f"Repository does not contain a {PLUGIN_META_FILENAME} file.")

    try:
        metadata = json.loads(meta_path.read_text())
    except Exception as exc:
        shutil.rmtree(install_dir, ignore_errors=True)
        raise PluginInstallError(f"Could not parse {PLUGIN_META_FILENAME}: {exc}") from exc

    django_app = metadata.get("django_app", "")
    if not django_app:
        shutil.rmtree(install_dir, ignore_errors=True)
        raise PluginInstallError(f"{PLUGIN_META_FILENAME} must specify a 'django_app' field.")

    # Update installed_plugins.py
    current_apps = _get_installed_plugin_apps()
    if django_app not in current_apps:
        current_apps.append(django_app)
        _write_installed_plugins_file(current_apps)

    # Create/update PluginInstall record
    try:
        from core.models import PluginInstall

        PluginInstall.objects.update_or_create(
            name=slug,
            defaults={
                "django_app": django_app,
                "label": metadata.get("label", slug),
                "source_type": PluginInstall.SOURCE_GIT,
                "source_url": git_url,
                "source_ref": ref or "",
                "version": metadata.get("version", ""),
                "last_synced_commit": commit,
                "last_synced_at": timezone.now(),
                "last_sync_status": PluginInstall.STATUS_SUCCESS,
                "last_sync_error": "",
            },
        )
    except Exception:
        logger.warning("Unable to persist plugin install record for %s", slug, exc_info=True)

    # Run migrations for the new app
    try:
        from django.core.management import call_command
        call_command("migrate", "--run-syncdb", verbosity=0)
    except Exception as exc:
        logger.warning("Could not run migrations after installing plugin %s: %s", slug, exc)

    _touch_wsgi()

    return PluginDefinition(
        name=metadata.get("name", slug),
        path=install_dir,
        label=metadata.get("label", slug),
        version=metadata.get("version", ""),
        description=metadata.get("description", ""),
        author=metadata.get("author", ""),
        django_app=django_app,
    )


def update_plugin_from_git(
    install,
    *,
    ref: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> PluginDefinition:
    """Update a git-installed plugin to the latest commit."""
    from core.models import PluginInstall

    if install.source_type != PluginInstall.SOURCE_GIT:
        raise PluginInstallError(f"Plugin {install.name} is not installed from git.")
    if not install.source_url:
        raise PluginInstallError(f"Plugin {install.name} missing source_url for git update.")

    ref_value = ref if ref is not None else (install.source_ref or "")
    plugins_root = get_plugins_root(base_dir)
    install_dir = plugins_root / install.name

    if install_dir.exists():
        shutil.rmtree(install_dir)

    _run_git(
        ["git", "clone", "--depth", "1", install.source_url, str(install_dir)],
        error_message="Unable to clone plugin repository",
    )
    if ref_value:
        _run_git(
            ["git", "-C", str(install_dir), "fetch", "--depth", "1", "origin", ref_value],
            error_message=f"Unable to fetch ref '{ref_value}'",
        )
        _run_git(
            ["git", "-C", str(install_dir), "checkout", ref_value],
            error_message=f"Unable to checkout ref '{ref_value}'",
        )

    commit = _run_git_capture(
        ["git", "-C", str(install_dir), "rev-parse", "HEAD"],
        error_message="Unable to determine plugin commit",
    )

    meta_path = install_dir / PLUGIN_META_FILENAME
    if not meta_path.exists():
        raise PluginInstallError(f"Repository does not contain a {PLUGIN_META_FILENAME} file.")

    try:
        metadata = json.loads(meta_path.read_text())
    except Exception as exc:
        raise PluginInstallError(f"Could not parse {PLUGIN_META_FILENAME}: {exc}") from exc

    update_fields = [
        "version",
        "last_synced_commit",
        "last_synced_at",
        "last_sync_status",
        "last_sync_error",
    ]
    install.version = metadata.get("version", "")
    install.last_synced_commit = commit
    install.last_synced_at = timezone.now()
    install.last_sync_status = PluginInstall.STATUS_SUCCESS
    install.last_sync_error = ""
    if ref is not None:
        install.source_ref = ref_value
        update_fields.append("source_ref")
    install.save(update_fields=update_fields)

    try:
        from django.core.management import call_command
        call_command("migrate", "--run-syncdb", verbosity=0)
    except Exception as exc:
        logger.warning("Could not run migrations after updating plugin %s: %s", install.name, exc)

    _touch_wsgi()

    return PluginDefinition(
        name=metadata.get("name", install.name),
        path=install_dir,
        label=metadata.get("label", install.name),
        version=metadata.get("version", ""),
        description=metadata.get("description", ""),
        author=metadata.get("author", ""),
        django_app=metadata.get("django_app", install.django_app),
    )


def remove_plugin(name: str, base_dir: Optional[Path] = None) -> None:
    """Remove a plugin from the filesystem and database."""
    plugins_root = get_plugins_root(base_dir)
    install_dir = plugins_root / name

    # Get the django_app before removing from DB
    django_app = ""
    try:
        from core.models import PluginInstall
        install = PluginInstall.objects.filter(name=name).first()
        if install:
            django_app = install.django_app
            install.delete()
    except Exception:
        logger.warning("Could not remove PluginInstall record for %s", name, exc_info=True)

    # Remove from installed_plugins.py
    if django_app:
        current_apps = _get_installed_plugin_apps()
        if django_app in current_apps:
            current_apps.remove(django_app)
            _write_installed_plugins_file(current_apps)

    # Remove filesystem directory
    if install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)

    _touch_wsgi()
