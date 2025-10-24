import markdown

from .models import SiteConfiguration

def site_configuration(request):
    settings = SiteConfiguration.get_solo()
    menu_items = settings.main_menu.menuitem_set.all()

    md = markdown.Markdown(extensions=["fenced_code"])
    settings.intro = md.convert(settings.intro)
    settings.bio = md.convert(settings.bio)

    return {
        "settings": settings,
        "menu_items": menu_items,
    }
