from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.utils.text import slugify


THEME_SETTINGS_FIELD_TYPES = {"string", "text", "boolean", "number", "color", "color_alpha", "select"}


@dataclass
class ThemeValidationIssue:
    code: str
    message: str
    hint: Optional[str] = None
    field: Optional[str] = None


@dataclass
class ThemeValidationResult:
    path: Path
    metadata: dict
    slug: Optional[str]
    errors: list[ThemeValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def summary(self, *, detailed: bool = False) -> str:
        parts: list[str] = []
        for issue in self.errors:
            if detailed and issue.hint:
                parts.append(f"{issue.message} ({issue.hint})")
            else:
                parts.append(issue.message)
        return "; ".join(parts)


def load_theme_metadata(meta_path: Path) -> tuple[dict, list[ThemeValidationIssue]]:
    if not meta_path.exists():
        return {}, [
            ThemeValidationIssue(
                code="missing_meta",
                field="theme.json",
                message="theme.json is missing.",
                hint="Include theme.json at the root of the theme.",
            )
        ]

    try:
        with meta_path.open() as handle:
            metadata = json.load(handle)
    except json.JSONDecodeError:
        return {}, [
            ThemeValidationIssue(
                code="invalid_meta",
                field="theme.json",
                message="theme.json is not valid JSON.",
                hint="Ensure theme.json contains a valid JSON object.",
            )
        ]
    except OSError as exc:
        return {}, [
            ThemeValidationIssue(
                code="meta_unreadable",
                field="theme.json",
                message=f"theme.json could not be read: {exc}",
            )
        ]

    if not isinstance(metadata, dict):
        return {}, [
            ThemeValidationIssue(
                code="invalid_meta",
                field="theme.json",
                message="theme.json must contain a JSON object.",
            )
        ]

    if not metadata:
        return {}, [
            ThemeValidationIssue(
                code="empty_meta",
                field="theme.json",
                message="theme.json is empty.",
            )
        ]

    return metadata, []


def validate_theme_dir(
    theme_dir: Path,
    *,
    expected_slug: Optional[str] = None,
    meta_filename: str = "theme.json",
    require_static: bool = True,
    require_directory_slug: bool = True,
) -> ThemeValidationResult:
    errors: list[ThemeValidationIssue] = []
    meta_path = theme_dir / meta_filename
    metadata, meta_errors = load_theme_metadata(meta_path)
    errors.extend(meta_errors)

    label = (metadata.get("label") or metadata.get("name")) if metadata else None
    if metadata and not label:
        errors.append(
            ThemeValidationIssue(
                code="missing_label",
                field="label",
                message="theme.json must include a 'label' or 'name'.",
            )
        )

    metadata_slug = metadata.get("slug") if metadata else None
    slug = slugify(metadata_slug) if metadata_slug else ""
    if metadata_slug is not None and not slug:
        errors.append(
            ThemeValidationIssue(
                code="invalid_slug",
                field="slug",
                message="theme.json must include a slug that slugifies to a value.",
            )
        )
    if not slug:
        if expected_slug:
            slug = slugify(expected_slug)
        else:
            slug = slugify(theme_dir.name)
    dir_slug = slugify(theme_dir.name)
    if require_directory_slug and metadata_slug and dir_slug and slug != dir_slug:
        errors.append(
            ThemeValidationIssue(
                code="slug_mismatch_directory",
                field="slug",
                message=f"Theme slug '{slug}' does not match directory name '{dir_slug}'.",
                hint="Rename the directory or update the slug in theme.json.",
            )
        )

    if expected_slug:
        expected = slugify(expected_slug)
        if metadata_slug and slug != expected:
            errors.append(
                ThemeValidationIssue(
                    code="slug_mismatch_expected",
                    field="slug",
                    message=f"Theme slug '{slug}' does not match expected slug '{expected}'.",
                )
            )
        slug = expected

    version = metadata.get("version") if metadata else None
    if version is not None and not isinstance(version, str):
        errors.append(
            ThemeValidationIssue(
                code="invalid_version",
                field="version",
                message="theme.json version must be a string if provided.",
            )
        )

    settings = metadata.get("settings") if metadata else None
    if settings is not None and not isinstance(settings, dict):
        errors.append(
            ThemeValidationIssue(
                code="invalid_settings",
                field="settings",
                message="theme.json settings must be a JSON object if provided.",
            )
        )
    elif isinstance(settings, dict):
        fields = settings.get("fields")
        if fields is not None and not isinstance(fields, dict):
            errors.append(
                ThemeValidationIssue(
                    code="invalid_settings_fields",
                    field="settings.fields",
                    message="theme.json settings.fields must be a JSON object if provided.",
                )
            )
        elif isinstance(fields, dict):
            for field_name, field_def in fields.items():
                if not isinstance(field_def, dict):
                    errors.append(
                        ThemeValidationIssue(
                            code="invalid_settings_field",
                            field=f"settings.fields.{field_name}",
                            message="Theme setting definitions must be JSON objects.",
                        )
                    )
                    continue
                field_type = field_def.get("type", "string")
                if not isinstance(field_type, str) or field_type not in THEME_SETTINGS_FIELD_TYPES:
                    errors.append(
                        ThemeValidationIssue(
                            code="invalid_settings_field",
                            field=f"settings.fields.{field_name}.type",
                            message="Theme setting type is not supported.",
                        )
                    )
                if field_type == "select":
                    choices = field_def.get("choices")
                    if choices is not None and not isinstance(choices, list):
                        errors.append(
                            ThemeValidationIssue(
                                code="invalid_settings_field",
                                field=f"settings.fields.{field_name}.choices",
                                message="Theme setting choices must be a list when provided.",
                            )
                        )

    templates_dir = theme_dir / "templates"
    if not templates_dir.exists() or not templates_dir.is_dir():
        errors.append(
            ThemeValidationIssue(
                code="missing_templates",
                message="Theme must include a templates/ directory.",
            )
        )

    static_dir = theme_dir / "static"
    if require_static and (not static_dir.exists() or not static_dir.is_dir()):
        errors.append(
            ThemeValidationIssue(
                code="missing_static",
                message="Theme must include a static/ directory.",
            )
        )

    return ThemeValidationResult(path=theme_dir, metadata=metadata, slug=slug or None, errors=errors)
