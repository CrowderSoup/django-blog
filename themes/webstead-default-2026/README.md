# Webstead Default 2026

The default Webstead theme, bundled with the install. This theme is intentionally verbose and annotated so you can copy it and delete anything you do not need.

This theme is **just** a theme. It contains templates, static assets, and documentation. There is no Django project bundled here.

## Why this exists

- Provide a clean, fresh starter that exercises most theme features.
- Demonstrate real template context variables and template tags.
- Make it obvious what is safe to delete when you are slimming down your own theme.

## Quick start

1. The theme ships with Webstead.

- You should already have `themes/webstead-default-2026/theme.json` on disk.

2. Activate it.

- In the admin UI: Settings > Themes > Active theme.

3. Fork or copy it if you want your own variant.

- Duplicate `themes/webstead-default-2026` into your `THEMES_ROOT`.
- Keep `theme.json` at the new theme root so it is discovered.

## Theme layout

- `theme.json` - metadata required for discovery.
- `templates/` - Django templates that override app templates.
- `static/` - theme assets (CSS, JS, images).
- `screenshot.png` - optional preview image (not used by the default admin UI).
- `LICENSE` - MIT license.

## Template map

These are the main files you will override or delete depending on your needs.

- `templates/base.html`: Global layout, head tags, nav, footer, and shared blocks.
- `templates/core/index.html`: Home page layout. Demonstrates `site_author_hcard` usage and the full posts feed.
- `templates/core/page.html`: Static pages with author and publish date.
- `templates/blog/posts.html`: Posts list + post kind filter UI + paginator.
- `templates/blog/post.html`: Post detail switcher for `note`, `photo`, and `article` kinds.
- `templates/blog/article.html`: Long-form article template.
- `templates/blog/article-summary.html`: Summary card used on listings.
- `templates/blog/note.html`: Short note template with minimal chrome.
- `templates/blog/photo.html`: Photo post template with a simple scrollable gallery.
- `templates/blog/activity.html`: Activity stream layout for replies, likes, and reposts.
- `templates/blog/activity-summary.html`: Compact activity card used on listings.
- `templates/blog/reply.html`: Reply detail template.
- `templates/blog/repost.html`: Repost detail template.
- `templates/blog/like.html`: Like detail template.
- `templates/blog/tags.html`: Tag list fragment used by multiple templates.
- `templates/blog/posts_by_tag.html`: Tag archive listing with paginator.
- `templates/blog/webmentions.html`: Webmention list.
- `templates/blog/webmention_form.html`: Webmention submission form.
- `templates/blog/comments_list.html`: Comments list.
- `templates/blog/comments_form.html`: Comment form.
- `templates/blog/interaction_forms.html`: Reply/repost/like forms.
- `templates/blog/interaction_forms_panel.html`: Condensed interaction form panel.
- `templates/blog/interaction-target.html`: Target context used by interaction templates.
- `templates/blog/bridgy_publish_links.html`: Bridgy Publish links for a post.
- `templates/blog/feed_item.html`: RSS item rendering.
- `templates/400.html`, `templates/403.html`, `templates/404.html`, `templates/500.html`: Error pages.
- `templates/indieauth/authorize.html`: IndieAuth authorization screen.
- `templates/indieauth/error.html`: IndieAuth error screen.
- `templates/micropub/indieauth_login.html`: Micropub IndieAuth login screen.

## Template context and tags

These are the most commonly used variables in this codebase. The templates show real usage.

- `settings`: Site configuration (title, tagline, menus, etc.).
- `menu_items`: Items from the main menu.
- `footer_menu_items`: Items from the footer menu.
- `feed_url`: Absolute URL to the posts feed when that route is available.
- `site_author_hcard`: Author h-card (photos, URLs, note).
- `site_author_display_name`: Best available author name.
- `post_kinds`, `selected_kinds`: Post filter controls.
- `post`: A single blog post (detail view).
- `posts`: A paginated list of posts (listing views).

Template tags used in this theme:

- `{% author_hcard_name %}`: Prefer h-card name, with a site-author fallback.

## Static assets

Theme assets are collected under `themes/<slug>/static/...` (relative to your `STATIC_URL`).

Example usage in templates:

```
<link rel="stylesheet" href="{% theme_static 'css/theme.css' %}">
```

## Theme settings

Settings live in `theme.json` and are injected into CSS variables in `templates/base.html`. Defaults match the current look.
Alpha-based colors use a color picker plus an opacity input in the theme settings UI.

**Core colors**
- `ink_color`: Primary text color.
- `muted_color`: Secondary text color.
- `inverse_text_color`: Text color on dark/accent surfaces.
- `paper_color`: Global background base.
- `panel_color`: Primary surface color.
- `line_color`: Borders and separators.

**Surface colors**
- `surface_cream_color`: Form and card cream surface.
- `surface_warm_color`: Warm neutral surface.
- `surface_accent_soft_color`: Soft accent surface.
- `surface_accent_soft_alt_color`: Alternate soft accent surface.
- `surface_accent_hover_color`: Accent hover surface.
- `activity_surface_color`: Activity card surface.
- `activity_border_color`: Activity card border.
- `interaction_surface_color`: Interaction card surface.
- `map_surface_color`: Activity map gradient start.
- `photo_dark_color`: Dark surface for photo frames (mobile).

**Accent colors**
- `accent_color`: Primary accent.
- `accent_deep_color`: Deeper accent for hover/contrast.

**Shadows and glass**
- `shadow_color`: Default drop shadow color.
- `accent_shadow_color`: Accent shadow.
- `accent_shadow_strong_color`: Strong accent shadow.
- `interaction_shadow_color`: Interaction card shadow.
- `input_shadow_color`: Input inset shadow.
- `focus_shadow_color`: Focus ring shadow.
- `scrollbar_shadow_color`: Scrollbar thumb color.
- `glass_light_color`: Translucent light surface.
- `glass_lighter_color`: Lighter translucent surface.
- `photo_dot_color`: Photo nav dot.
- `photo_dot_active_color`: Active photo nav dot.

**Background**
- `background_gradient_start`: Gradient start.
- `background_gradient_mid`: Gradient midpoint.
- `background_gradient_end`: Gradient end.
- `show_background_pattern`: Toggle the pattern overlay.

**Typography**
- `font_body`: Body font stack.
- `font_heading`: Heading font stack.
- `font_mono`: Monospace font stack.

**Radii**
- `radius_sm`: Small radius.
- `radius_md`: Medium radius.
- `radius_lg`: Large radius.
- `radius_xl`: Extra large radius.
- `radius_pill`: Pill radius.

## Notes for forkers

- Delete any template you do not need. Django will fall back to the built-in app templates.
- Keep `theme.json` at the root or the theme will not be discovered.
- If you do not want external fonts, remove the `@import` line in `static/css/theme.css`.
- This theme includes IndieWeb endpoints plus the combined analytics/admin bar script (`js/webstead.js`) in `base.html`.
- The photo gallery is intentionally lightweight and scrollable for accessibility.

## Defaults and discovery

- The default theme slug is `webstead-default-2026` (see `core/themes.py`).
- If no active theme is selected, Webstead falls back to the default slug automatically.
- Theme discovery expects `theme.json` at the theme root (`themes/<slug>/theme.json`).

## License

MIT. See `LICENSE`.
