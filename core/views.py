import markdown

from django.shortcuts import render, get_object_or_404

from .models import Page

def index(request):
    return render(request, 'core/index.html')

def page(request, slug):
    page = get_object_or_404(
        Page.objects.only("title", "content", "slug", "published_on"),
        slug=slug,
    )

    md = markdown.Markdown(extensions=["fenced_code"])
    page.content = md.convert(page.content)

    return render(request, 'core/page.html', { "page": page })
