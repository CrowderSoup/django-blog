import logging

from django import template
from django.utils.safestring import mark_safe

register = template.Library()
logger = logging.getLogger(__name__)


@register.simple_tag(takes_context=True)
def render_widget_area(context, area_slug: str) -> str:
    from core.plugins import registry
    from widgets.models import WidgetInstance

    active_theme = context.get("active_theme")
    if active_theme:
        declared = {a.get("slug") for a in getattr(active_theme, "widget_areas", [])}
        if area_slug not in declared:
            return ""

    request = context.get("request")
    instances = WidgetInstance.objects.filter(area=area_slug, is_active=True).order_by("order", "pk")
    parts = []
    for inst in instances:
        cls = registry.get_widget_type(inst.widget_type)
        if cls:
            try:
                parts.append(cls().render(inst.config or {}, request=request))
            except Exception:
                logger.exception(
                    "Widget %s pk=%s failed to render", inst.widget_type, inst.pk
                )
    return mark_safe("".join(parts))
