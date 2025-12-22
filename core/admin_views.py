from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django import forms
from django.contrib import messages
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .theme_sync import reconcile_installed_themes
from .themes import (
    ThemeUploadError,
    create_theme_file,
    delete_theme_path,
    discover_themes,
    ingest_theme_archive,
    list_theme_directories,
    list_theme_files,
    read_theme_file,
    save_theme_file,
    sync_themes_from_storage,
)

ALLOWED_SUFFIXES = (".html", ".htm", ".txt", ".xml", ".md", ".css", ".js", ".json")


class ThemeUploadForm(forms.Form):
    archive = forms.FileField(
        help_text="Upload a .zip containing theme.json plus templates/ and static/ folders."
    )

    def clean_archive(self):
        file = self.cleaned_data["archive"]
        if not file.name.lower().endswith(".zip"):
            raise forms.ValidationError("Only .zip theme archives are supported.")
        return file


class ThemeFileForm(forms.Form):
    theme = forms.ChoiceField(label="Theme")
    path = forms.ChoiceField(label="File")
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 25, "class": "w-full font-mono"}))

    def __init__(self, theme_choices, path_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["theme"].choices = theme_choices
        self.fields["path"].choices = [(path, path) for path in path_choices]
        if not path_choices:
            self.fields["path"].required = False


@dataclass
class ThemeFileSelection:
    slug: str
    path: Optional[str]
    content: str = ""


def _theme_choices():
    return [(theme.slug, theme.label) for theme in discover_themes()]


def theme_manager(request: HttpRequest, admin_site) -> HttpResponse:
    upload_form = ThemeUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and request.POST.get("action") == "check_theme_storage":
        restored: list[str] = []
        failures: list[str] = []
        storage_synced: list[str] = []

        try:
            from .models import ThemeInstall

            results = reconcile_installed_themes()
            restored = [result.slug for result in results if result.restored]
            failures = [result.slug for result in results if result.status == ThemeInstall.STATUS_FAILED]
        except Exception as exc:  # pragma: no cover - defensive
            messages.error(request, f"Unable to check theme installs: {exc}")

        try:
            storage_synced = sync_themes_from_storage()
        except Exception as exc:  # pragma: no cover - defensive
            messages.warning(request, f"Unable to check theme storage: {exc}")

        if restored:
            restored_slugs = sorted(set(restored))
            restored_list = ", ".join(restored_slugs)
            messages.success(
                request, f"Restored {len(restored_slugs)} theme(s) from installs: {restored_list}."
            )
        if storage_synced:
            storage_slugs = sorted(set(storage_synced))
            storage_list = ", ".join(storage_slugs)
            messages.success(
                request, f"Synced {len(storage_slugs)} theme(s) from storage: {storage_list}.",
            )
        if failures:
            messages.warning(request, f"Theme installs still failing for: {', '.join(sorted(set(failures)))}.")
        elif not any([restored, storage_synced]):
            messages.info(request, "No themes found in installs or storage to sync.")

        return redirect(reverse("admin:core_theme_list"))

    if request.method == "POST" and upload_form.is_valid():
        try:
            theme = ingest_theme_archive(upload_form.cleaned_data["archive"])
            messages.success(
                request,
                f"Theme '{theme.label}' ({theme.slug}) uploaded and synced to storage.",
            )
            return redirect(reverse("admin:core_theme_list"))
        except ThemeUploadError as exc:
            upload_form.add_error("archive", exc)
        except Exception as exc:  # pragma: no cover - defensive
            upload_form.add_error("archive", f"Unexpected error: {exc}")

    themes = discover_themes()
    file_counts = {theme.slug: len(list_theme_files(theme.slug, suffixes=ALLOWED_SUFFIXES)) for theme in themes}
    theme_rows = [(theme, file_counts.get(theme.slug, 0)) for theme in themes]

    context = {
        **admin_site.each_context(request),
        "title": "Themes",
        "upload_form": upload_form,
        "themes": themes,
        "theme_rows": theme_rows,
    }
    return TemplateResponse(request, "admin/themes/manage.html", context)


def _build_selection(request: HttpRequest, slug_param: Optional[str]) -> ThemeFileSelection:
    themes = discover_themes()
    default_slug = slug_param or request.GET.get("theme") or (themes[0].slug if themes else "")
    selected_slug = request.POST.get("theme", default_slug)

    files = list_theme_files(selected_slug, suffixes=ALLOWED_SUFFIXES) if selected_slug else []
    default_path = request.GET.get("path") or (files[0] if files else None)
    selected_path = request.POST.get("path") or default_path

    content = ""
    if selected_slug and selected_path:
        try:
            content = read_theme_file(selected_slug, selected_path)
        except ThemeUploadError as exc:
            messages.error(request, str(exc))
        except UnicodeDecodeError:
            messages.error(request, "That file cannot be edited as text.")

    return ThemeFileSelection(slug=selected_slug or "", path=selected_path, content=content)


def theme_file_edit(request: HttpRequest, slug: Optional[str] = None, admin_site=None) -> HttpResponse:
    themes = discover_themes()
    if not themes:
        messages.warning(request, "Upload a theme first to enable editing.")
        return redirect(reverse("admin:core_theme_list"))

    theme_choices = _theme_choices()

    selection = _build_selection(request, slug)
    file_choices = list_theme_files(selection.slug, suffixes=ALLOWED_SUFFIXES) if selection.slug else []
    directory_choices = list_theme_directories(selection.slug) if selection.slug else []
    path_choices = sorted(set(file_choices + directory_choices))

    form_initial = {"theme": selection.slug, "path": selection.path, "content": selection.content}
    form = ThemeFileForm(theme_choices, path_choices, request.POST or None, initial=form_initial)

    if request.method == "POST" and form.is_valid():
        chosen_theme = form.cleaned_data["theme"]
        chosen_path = form.cleaned_data.get("path") or ""
        requested_name = (request.POST.get("new_entry_name") or "").strip().rstrip("/")

        if "load" in request.POST:
            return redirect(
                f"{reverse('admin:core_theme_edit', kwargs={'slug': chosen_theme})}?path={chosen_path}"
            )

        if "new_file" in request.POST:
            if not requested_name:
                messages.error(request, "Provide a name for the new file.")
                return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))
            if requested_name.startswith("/") or "\\" in requested_name or ".." in requested_name:
                messages.error(request, "Paths cannot start with '/' or contain backslashes or '..'.")
                return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))

            target_dir = Path(chosen_path).parent if chosen_path else Path("")
            target_relative = (target_dir / requested_name).as_posix()

            try:
                if ALLOWED_SUFFIXES and Path(requested_name).suffix not in ALLOWED_SUFFIXES:
                    allowed = ", ".join(ALLOWED_SUFFIXES)
                    messages.error(request, f"Files must use one of the allowed extensions: {allowed}")
                    return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))
                create_theme_file(chosen_theme, target_relative)
                messages.success(request, f"Created file {target_relative} in {chosen_theme}.")
                next_path = target_relative
                return redirect(
                    f"{reverse('admin:core_theme_edit', kwargs={'slug': chosen_theme})}?path={next_path}"
                    if next_path
                    else reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme})
                )
            except ThemeUploadError as exc:
                messages.error(request, str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                messages.error(request, f"Unable to create entry: {exc}")
            return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))

        if "delete" in request.POST:
            if not chosen_path:
                messages.error(request, "Select a file to delete.")
                return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))
            try:
                delete_theme_path(chosen_theme, chosen_path)
                messages.success(request, f"Deleted {chosen_path} from {chosen_theme}.")
                next_path = next((p for p in file_choices if p != chosen_path), None)
                redirect_url = (
                    f"{reverse('admin:core_theme_edit', kwargs={'slug': chosen_theme})}?path={next_path}"
                    if next_path
                    else reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme})
                )
                return redirect(redirect_url)
            except ThemeUploadError as exc:
                messages.error(request, str(exc))
            except Exception as exc:  # pragma: no cover - defensive
                messages.error(request, f"Unable to delete path: {exc}")
            return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))

        if "save" not in request.POST:
            messages.error(request, "Use the Save file button to persist changes.")
            return redirect(
                f"{reverse('admin:core_theme_edit', kwargs={'slug': chosen_theme})}?path={chosen_path}"
            )

        if not chosen_path:
            messages.error(request, "Select a file to edit for this theme.")
            return redirect(reverse("admin:core_theme_edit", kwargs={"slug": chosen_theme}))

        try:
            save_theme_file(chosen_theme, chosen_path, form.cleaned_data["content"])
            messages.success(request, f"Saved {chosen_path} in {chosen_theme}.")
            return redirect(
                f"{reverse('admin:core_theme_edit', kwargs={'slug': chosen_theme})}?path={chosen_path}"
            )
        except ThemeUploadError as exc:
            messages.error(request, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            messages.error(request, f"Unable to save file: {exc}")

    context = {
        **admin_site.each_context(request),
        "title": "Edit theme files",
        "form": form,
        "themes": themes,
        "theme_choices": theme_choices,
        "file_choices": file_choices,
        "selection": selection,
    }
    return TemplateResponse(request, "admin/themes/edit.html", context)


def theme_install_list(request: HttpRequest, admin_site) -> HttpResponse:
    from .models import ThemeInstall

    source_type = (request.GET.get("source_type") or "").strip()
    status = (request.GET.get("status") or "").strip()
    query = (request.GET.get("q") or "").strip()

    installs = ThemeInstall.objects.all()
    if source_type in dict(ThemeInstall.SOURCE_CHOICES):
        installs = installs.filter(source_type=source_type)
    if status in dict(ThemeInstall.STATUS_CHOICES):
        installs = installs.filter(last_sync_status=status)
    if query:
        installs = installs.filter(
            models.Q(slug__icontains=query)
            | models.Q(source_url__icontains=query)
            | models.Q(source_ref__icontains=query)
        )

    rows = [
        {
            "install": install,
            "source_url": install.safe_source_url(),
            "source_ref": install.source_ref,
        }
        for install in installs.order_by("slug")
    ]

    context = {
        **admin_site.each_context(request),
        "title": "Theme installs",
        "installs": rows,
        "filters": {
            "source_type": source_type,
            "status": status,
            "q": query,
        },
        "source_choices": ThemeInstall.SOURCE_CHOICES,
        "status_choices": ThemeInstall.STATUS_CHOICES,
    }
    return TemplateResponse(request, "admin/themes/installs.html", context)


def theme_install_detail(request: HttpRequest, slug: str, admin_site) -> HttpResponse:
    from .models import ThemeInstall

    install = get_object_or_404(ThemeInstall, slug=slug)
    context = {
        **admin_site.each_context(request),
        "title": f"Theme install: {install.slug}",
        "install": install,
        "source_url": install.safe_source_url(),
    }
    return TemplateResponse(request, "admin/themes/install_detail.html", context)
