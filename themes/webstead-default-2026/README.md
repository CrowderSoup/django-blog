# Webstead Default 2026

A reference theme for the Webstead blog engine. This repo is intentionally verbose and annotated so you can fork it and delete anything you do not need.

This theme is **just** a theme. It contains templates, static assets, and documentation. There is no Django project bundled here.

## Why this exists

- Provide a clean, fresh starter that exercises most theme features.
- Demonstrate real template context variables and template tags.
- Make it obvious what is safe to delete when you are slimming down your own theme.

## Quick start

1. Install the theme from git.

- In the admin UI: Settings > Themes > Install from git.
- URL: your fork (example: `https://github.com/you/webstead-default-2026`)
- Slug: `webstead-default-2026`

2. Or place it on disk manually.

- Copy this repo to your `THEMES_ROOT` directory.
- The final path should look like: `THEMES_ROOT/webstead-default-2026/theme.json`

3. Activate it.

- In the admin UI: Settings > Themes > Active theme.

## Theme layout

- `theme.json` - metadata required for discovery.
- `templates/` - Django templates that override app templates.
- `static/` - theme assets (CSS, JS, images).
- `LICENSE` - MIT license.

## Template map

These are the main files you will override or delete depending on your needs.

- `templates/base.html`
  - Global layout, head tags, nav, footer, and shared blocks.
- `templates/core/index.html`
  - Home page layout. Demonstrates `site_author_hcard` usage and recent posts.
- `templates/core/page.html`
  - Static pages with author and publish date.
- `templates/blog/posts.html`
  - Posts list + post kind filter UI + paginator.
- `templates/blog/post.html`
  - Post detail switcher for `note`, `photo`, and `article` kinds.
- `templates/blog/article.html`
  - Long-form article template.
- `templates/blog/article-summary.html`
  - Summary card used on listings.
- `templates/blog/note.html`
  - Short note template with minimal chrome.
- `templates/blog/photo.html`
  - Photo post template with a simple scrollable gallery.
- `templates/blog/tags.html`
  - Tag list fragment used by multiple templates.
- `templates/blog/posts_by_tag.html`
  - Tag archive listing with paginator.
- `templates/400.html`, `templates/403.html`, `templates/404.html`, `templates/500.html`
  - Error pages to keep the theme consistent even when something goes wrong.

## Template context and tags

These are the most commonly used variables in this codebase. The templates show real usage.

- `settings` - site configuration (title, tagline, menus, etc.).
- `menu_items` - items from the main menu.
- `footer_menu_items` - items from the footer menu.
- `feed_url` - RSS feed URL (when available).
- `site_author_hcard` - author h-card (photos, URLs, note).
- `site_author_display_name` - best available author name.
- `post_kinds`, `selected_kinds`, `selected_kinds_query` - post filter controls.
- `post` - a single blog post (detail view).
- `posts` - a paginated list of posts (listing views).

Template tags used in this theme:

- `{% author_hcard_name %}` - prefer h-card name, with a site-author fallback.

## Static assets

The theme static files are served under `themes/<slug>/...`.

Example usage in templates:

```
<link rel="stylesheet" href="{% theme_static 'css/theme.css' %}">
```

## Notes for forkers

- Delete any template you do not need. Django will fall back to the built-in app templates.
- Keep `theme.json` at the root or the theme will not be discovered.
- If you do not want external fonts, remove the `@import` line in `static/css/theme.css`.
- This theme keeps IndieWeb endpoints and analytics beacons in `base.html` for parity with the default templates.
- The photo gallery is intentionally lightweight and scrollable for accessibility.

## License

MIT. See `LICENSE`.
