from django.contrib import admin

from markdownx.admin import MarkdownxModelAdmin
from solo.admin import SingletonModelAdmin

from .models import Page, Menu, MenuItem, SiteConfiguration

admin.site.register(SiteConfiguration, SingletonModelAdmin)
admin.site.register(Page, MarkdownxModelAdmin)
admin.site.register(Menu)
admin.site.register(MenuItem)
