from __future__ import annotations

from abc import ABC, abstractmethod


class BaseWidget(ABC):
    slug: str = ""
    label: str = ""
    config_schema: dict = {}
    template_name: str = ""

    @abstractmethod
    def render(self, config: dict, request=None) -> str: ...


class BasePlugin:
    name: str = ""
    label: str = ""
    version: str = "1.0.0"
    description: str = ""

    def get_widget_types(self) -> list[type[BaseWidget]]:
        return []

    def get_admin_nav_items(self) -> list[dict]:
        """Items to inject into the admin sidebar.
        Each dict: {"label": str, "url_name": str, "icon": str (optional)}
        """
        return []


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        self._plugins[plugin.name] = plugin

    def all_plugins(self) -> list[BasePlugin]:
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> BasePlugin | None:
        return self._plugins.get(name)

    def get_all_widget_types(self) -> list[type[BaseWidget]]:
        types = []
        for plugin in self._plugins.values():
            types.extend(plugin.get_widget_types())
        return types

    def get_widget_type(self, slug: str) -> type[BaseWidget] | None:
        for cls in self.get_all_widget_types():
            if cls.slug == slug:
                return cls
        return None

    def widget_choices(self) -> list[tuple[str, str]]:
        return [(cls.slug, cls.label) for cls in self.get_all_widget_types()]

    def get_admin_nav_items(self) -> list[dict]:
        items = []
        for plugin in self._plugins.values():
            items.extend(plugin.get_admin_nav_items())
        return items


registry = PluginRegistry()
