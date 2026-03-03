from core.plugins import BasePlugin


class WidgetsPlugin(BasePlugin):
    name = "widgets"
    label = "Widgets"
    description = "Configurable widget areas for the site."

    def get_widget_types(self):
        from .widget_types import TextWidget, RecentPostsWidget, ProfileWidget
        return [TextWidget, RecentPostsWidget, ProfileWidget]

    def get_admin_nav_items(self):
        return [{"label": "Widgets", "url_name": "site_admin:widget_list"}]
