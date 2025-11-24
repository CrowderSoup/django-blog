from django.contrib import admin

from files.admin import AttachmentInline
from .models import Post, Tag


class PublishedStatusFilter(admin.SimpleListFilter):
    title = "Published status"
    parameter_name = "published"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Published"),
            ("no", "Unpublished"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(published_on__isnull=True)
        if self.value() == "no":
            return queryset.filter(published_on__isnull=True)
        return queryset


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ("kind", PublishedStatusFilter)
    inlines = [AttachmentInline]

admin.site.register(Tag)
