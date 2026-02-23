# Theme Author Guide

This guide is for designers and developers building themes. It explains how themes are structured, how they interact with the system, and how to design themes that are flexible, safe, and pleasant to use.

This guide is intentionally practical and example-driven. For strict rules and validation requirements, refer to the Theme Spec.

---

## What Is a Theme?

A theme controls **presentation only**. It defines:

- HTML templates
- CSS and other static assets
- Optional, user-configurable theme settings

A theme **does not**:

- Contain business logic
- Define content models
- Store data
- Change application behavior (with two exceptions: `home_feed_mode` and `home_feed_redirect` — see System-Recognized Theme Settings in the Theme Spec)

If something affects how data is fetched, stored, or processed, it does not belong in a theme.

---

## Theme Directory Basics

Every theme lives in its own directory under `themes/`:

```
themes/
  └── my-theme/
      ├── theme.json
      ├── static/
      └── templates/
```

- The directory name is the theme's **slug**
- The theme is identified and discovered via `theme.json`
- Templates and static assets are only used when the theme is active

You can safely assume:

- Only one theme is active at a time
- Templates are never mixed between themes

---

## `theme.json`: Your Theme's Contract

`theme.json` is the public contract between your theme and the system.

Use it to:

- Name and describe your theme
- Declare configurable settings
- Expose metadata to templates

Keep it small and stable. Changing keys later can break existing sites.

### Minimal example

```json
{
  "label": "My Theme"
}
```

This is a valid theme.

---

## Theme Settings: Designing for Flexibility

Theme settings let site owners customize presentation without editing code.

Good candidates for settings:

- Colors
- Font stacks
- Layout widths
- Toggles for optional UI elements

Bad candidates:

- Content
- Feature flags
- Anything that changes application behavior

### Defining settings

```json
{
  "settings": {
    "fields": {
      "accent_color": {
        "type": "color",
        "label": "Accent color",
        "default": "#cc3f2e"
      },
      "overlay_shadow": {
        "type": "color_alpha",
        "label": "Overlay shadow",
        "default": "rgba(0, 0, 0, 0.08)"
      }
    }
  }
}
```

Supported field types: `string`, `text`, `boolean`, `number`, `color`, `color_alpha`, `select`.

Use `color_alpha` when you need CSS colors with opacity (e.g. `rgba(...)` values). Use `color` for opaque hex colors.

Guidelines:

- Always provide sensible defaults
- Prefer fewer settings over more
- Settings should feel safe to change

---

## Using Settings in Templates

When your theme is active, settings are available as `theme.settings`.

```html
<style>
  :root {
    --accent: {{ theme.settings.accent_color|default:"#cc3f2e" }};
    --shadow: {{ theme.settings.overlay_shadow|default:"rgba(0,0,0,0.08)" }};
  }
</style>
```

Best practices:

- Treat settings as optional
- Always guard with defaults
- Centralize CSS variables instead of scattering settings throughout templates

---

## Template Tag Loading

The `theme` tag library (`theme_static`) is registered as a Django template **builtin** — you do **not** need `{% load theme %}` in your templates. `theme_static` is always available.

The `author` tag library (`author_hcard_name`) **must** be explicitly loaded:

```html
{% load author %}
```

---

## Template Context: What's Available

Templates receive a mix of standard Django context plus site- and theme-specific data. Context varies by view; always guard optional fields.

### Standard Django context

Available on most views:

- `request` — the current request object
- `user` — the authenticated user, if any
- `messages` — Django messages framework
- `now` — current datetime (provided by Django's `django.template.context_processors.now`)

### Site configuration context

Provided by the `core.context_processors.site_configuration` context processor:

- `settings` — the `SiteConfiguration` object (see fields below)
- `menu_items` — queryset of `MenuItem` objects for the main menu, or `None`
- `footer_menu_items` — queryset of `MenuItem` objects for the footer menu, or `None`
- `feed_url` — absolute URL to the posts RSS feed, or `None`
- `home_feed_mode` — `"home"` or `"blog"` (from active theme settings)
- `posts_index_url` — absolute URL to the posts listing (may redirect to `/` if `home_feed_redirect` is active)
- `site_author_hcard` — the primary `HCard` object for the site author, or `None`
- `site_author_display_name` — resolved display name string for the site author
- `og_default_image` — absolute URL string for the default Open Graph image

### Theme context

Provided by the `core.context_processors.theme` context processor:

- `active_theme` — the active `ThemeDefinition` object, or `None`
- `theme.slug` — the theme slug
- `theme.label` — the human-friendly label
- `theme.metadata` — all extra keys from `theme.json`
- `theme.settings` — resolved settings dict with defaults applied
- `theme.settings_schema` — raw settings schema from `theme.json`
- `theme.template_prefix` — prefix for `{% include %}` paths
- `theme.static_prefix` — prefix for static assets

### `SiteConfiguration` fields

The `settings` object in templates is the `SiteConfiguration` singleton. Fields available:

- `settings.title` — site name
- `settings.tagline` — site tagline
- `settings.home_page` — a `Page` object if a custom home page is set, or `None`
- `settings.favicon` — a `File` object if a favicon is configured, or `None`
- `settings.site_author` — the designated author user, or `None`
- `settings.comments_enabled` — boolean
- `settings.developer_tools_enabled` — boolean
- `settings.bridgy_publish_bluesky`, `settings.bridgy_publish_mastodon`, etc. — Bridgy publish toggles (booleans)

### `MenuItem` fields

Each item in `menu_items` and `footer_menu_items`:

- `item.text` — link label
- `item.url` — link href
- `item.weight` — sort order (items are pre-sorted)

### Quick examples

```html
<title>{{ settings.title }}{% if settings.tagline %} — {{ settings.tagline }}{% endif %}</title>
```

```html
<link rel="alternate" type="application/rss+xml" href="{{ feed_url }}">
```

```html
{% if site_author_hcard %}
  <p>By {{ site_author_display_name }}</p>
{% endif %}
```

```html
<link rel="stylesheet" href="{% theme_static 'css/theme.css' %}">
```

```html
{% for item in menu_items %}
  <a href="{{ item.url }}">{{ item.text }}</a>
{% endfor %}
```

---

## Blog Post Templates: Context and Model Fields

The single post template lives at `blog/post.html` and receives the following context.

### Core post context

- `post` — the `Post` model instance (see fields below)
- Standard context (site configuration, theme settings, etc.)

### `Post` fields and helpers

Core fields:

- `post.title`, `post.slug`, `post.content`
- `post.kind` — one of `article`, `note`, `photo`, `activity`, `like`, `repost`, `reply`, `event`, `rsvp`, `checkin`, `bookmark`
- `post.published_on` — datetime, or `None` if draft
- `post.deleted` — boolean
- `post.like_of`, `post.repost_of`, `post.in_reply_to`, `post.bookmark_of` — URLs for interaction posts (empty string if not applicable)
- `post.mf2` — microformats2 JSON payload dict (may be empty)

Relations and helpers:

- `post.author` — user; may be `None`
- `post.author.hcards` — prefetched; use for author display (access name via `{% author_hcard_name post.author %}`)
- `post.tags` — many-to-many; use `post.tags.all` in templates
- `post.attachments` — generic relation; use `post.attachments.all`
- `post.photo_attachments` — property: attachments filtered to `role="photo"`
- `post.gpx_attachment` — property: first attachment with `role="gpx"`, or `None`
- `post.html()` — markdown rendered to safe HTML (fenced code blocks supported)
- `post.summary()` — plain-text excerpt, max ~500 chars
- `post.is_published()` — boolean; `True` when `published_on` is set
- `post.get_absolute_url()` — URL to the post detail page

### Activity context

Set when `post.kind == "activity"`:

- `activity` — dict with keys:
  - `activity.name` — activity type string (e.g. `"Run"`, `"Ride"`)
  - `activity.track_url` — URL to GPX track or external activity link
- `activity_photos` — list of `Attachment` objects with `role="photo"`

### Checkin context

Set when `post.kind == "checkin"`:

- `checkin_photos` — list of `Attachment` objects with `role="photo"`
- `checkin_data` — dict from `post.mf2["checkin"]`, or `None`

### Event context

Set when `post.kind == "event"`:

- `event_data` — dict from `post.mf2["event"]`, or `None`

### RSVP context

Set when `post.kind == "rsvp"`:

- `rsvp_value` — string from `post.mf2["rsvp"]`, or `None`

### Interaction context

Set when `post.kind` is `like`, `repost`, `reply`, `bookmark`, or `rsvp`:

- `post.interaction` — dict dynamically attached to the post object:
  - `post.interaction.kind` — the post kind string
  - `post.interaction.label` — e.g. `"Liked"`, `"Reposted"`, `"Replying to"`, `"Bookmarked"`, `"RSVP to"`
  - `post.interaction.target_url` — the URL being interacted with
  - `post.interaction.target` — dict with `title`, `summary_text`, `summary_excerpt`, `summary_truncated` when the target was fetchable; `None` otherwise
  - `post.interaction.show_content` — bool; `False` when the post content is just the default auto-generated text (e.g. "Liked {url}") and should be hidden

### Webmention context

- `webmention_replies` — list of dicts, each with: `source`, `created_at`, `author_name`, `author_url`, `author_photo`, `excerpt`
- `webmention_likes` — list of `Webmention` model instances (accepted likes)
- `webmention_reposts` — list of `Webmention` model instances (accepted reposts)
- `webmention_total` — integer count of all webmentions
- `webmention_target` — absolute URL of the post (for the webmention form action)
- `webmention_next` — relative URL of the post (for the webmention redirect)

### Comments context

- `approved_comments` — queryset of approved `Comment` objects, ordered by `created_at`
- `comment_form` — a `CommentForm` instance (only present when comments are enabled and configured)
- `comments_enabled` — boolean
- `comments_configured` — boolean; `True` when comments are enabled AND the required spam protection keys are set
- `turnstile_site_key` — Cloudflare Turnstile site key string (may be empty in development)
- `comments_debug` — boolean; `True` in DEBUG mode (Turnstile and Akismet checks are skipped)

`Comment` model fields (for `approved_comments`):

- `comment.author_name`, `comment.author_url`, `comment.author_email`
- `comment.content` — raw text
- `comment.excerpt` — truncated text excerpt
- `comment.created_at` — datetime

### IndieAuth context

- `indieauth_me` — the logged-in IndieAuth user's me URL from session, or `None`
- `indieauth_login_url` — URL to the IndieAuth login page, pre-configured to return to the current post

### Open Graph context

All OG values default gracefully in `base.html` via the `{% with %}` tag if not explicitly set:

- `og_title` — page title
- `og_description` — short description
- `og_image` — absolute image URL
- `og_image_alt` — image alt text
- `og_url` — canonical URL
- `og_type` — `"article"` for articles, `"website"` for other post kinds

---

## Posts Listing Template: Context

The posts listing template lives at `blog/posts.html`.

- `posts` — Django `Page` object (paginator page) containing `Post` instances
- `post_kinds` — list of `(value, label)` tuples for all post kind choices
- `selected_kinds` — list of currently filtered kind strings
- `selected_tags` — list of currently filtered tag strings
- `default_kinds` — list of kind strings active when no filter is applied (configurable via the site settings; defaults to `article`, `note`, `photo`, `activity`, `event`, `checkin`)
- `filter_query` — URL-encoded query string for pagination links
- `feed_filter_query` — URL-encoded query string for the RSS feed link
- `has_active_filters` — boolean; `True` when any filter is applied
- `has_activity` — boolean; `True` when any post in the current page is an activity post

**Dynamic per-post attributes in the listing:**

For posts in the listing queryset, the view dynamically attaches attributes directly to the post object:

- `post.activity` — set for activity posts (same dict as in single post view)
- `post.event_data` — set for event posts (from `post.mf2["event"]`)
- `post.checkin_data` — set for checkin posts (from `post.mf2["checkin"]`)
- `post.interaction` — set for like/reply/repost/bookmark posts (same dict as in single post view)

These are not model properties — they are attached at request time. Guard them in templates:

```html
{% if post.kind == 'activity' and post.activity %}
  <p>{{ post.activity.name }}</p>
{% endif %}
```

Pagination (standard Django paginator):

```html
{% if posts.has_previous %}
  <a href="?page={{ posts.previous_page_number }}">Newer</a>
{% endif %}
<span>Page {{ posts.number }} of {{ posts.paginator.num_pages }}</span>
{% if posts.has_next %}
  <a href="?page={{ posts.next_page_number }}">Older</a>
{% endif %}
```

---

## Index Template: Context

The home page template lives at `core/index.html`.

Always available:

- `recent_posts` — queryset of last 5 published articles
- `home_page` — a `Page` object if a custom home page is set in settings, or `None`

When `home_feed_mode` is `"home"` (set via theme settings), the full posts listing context is also merged into the index context. This means all variables from the Posts Listing context above are available in `core/index.html` as well. Use this to build a single-page feed layout.

---

## Page Templates: Context and Model Fields

The page template lives at `core/page.html` and receives:

- `page` — the `Page` model instance
- Standard context listed above (site configuration, theme settings, etc.)
- Open Graph context (`og_title`, `og_description`, `og_image`, `og_image_alt`, `og_url`, `og_type`)

### `Page` fields and helpers

- `page.title`, `page.slug`, `page.content`
- `page.published_on` — datetime
- `page.is_gallery` — boolean; `True` when the page is designated as a photo gallery
- `page.author` — user; may be `None`
- `page.author.hcards` — prefetched; use for author display
- `page.attachments` — generic relation; use `page.attachments.all`
- `page.html()` — markdown rendered to safe HTML

---

## Attachments and Assets

Both posts and pages use `Attachment` objects linked to `File` assets:

- `attachment.asset` — the `File` object
- `attachment.asset.file.url` — file URL
- `attachment.asset.alt_text` — alt text string
- `attachment.asset.caption` — caption string
- `attachment.asset.kind` — `"image"`, `"doc"`, or `"video"`
- `attachment.role` — theme-defined role like `"photo"`, `"hero"`, `"inline"`, `"gallery"`, `"gpx"`
- `attachment.sort_order` — integer; attachments are pre-sorted by this

---

## Author Data and IndieWeb Conventions

### Author h-cards

The `site_author_hcard` context variable is an `HCard` model instance. Notable fields:

- `site_author_hcard.name` — display name
- `site_author_hcard.note` — bio text (markdown)
- `site_author_hcard.note_html` — bio rendered to safe HTML (pre-rendered by the context processor)
- `site_author_hcard.photos` — related `HCardPhoto` objects
- `site_author_hcard.primary_photo` — the first `HCardPhoto`, or `None`
- `site_author_hcard.primary_photo_url` — URL string of the primary photo, or `""`
- `site_author_hcard.urls` — related `HCardUrl` objects
- `site_author_hcard.emails` — related `HCardEmail` objects

`HCardUrl` fields:

- `url.value` — raw URL or email string
- `url.href` — URL with `mailto:` prefix automatically applied for email kind
- `url.kind` — one of `"x"`, `"bsky"`, `"email"`, `"mastodon"`, `"github"`, `"instagram"`, `"other"`

Use the `author_hcard_name` template tag instead of accessing h-card name directly:

```html
{% load author %}

<p>By {% author_hcard_name post.author %}</p>
```

This ensures proper h-card resolution and graceful fallback to the site author.

### IndieWeb endpoints in `base.html`

Your `base.html` should include the IndieWeb endpoint links. These enable Micropub clients, IndieAuth, and Webmention:

```html
<link rel="indieauth-metadata" href="{% url 'indieauth-metadata' %}">
<link rel="authorization_endpoint" href="{% url 'indieauth-authorize' %}">
<link rel="token_endpoint" href="{% url 'indieauth-token' %}">
<link rel="micropub" href="{% url 'micropub-endpoint' %}">
<link rel="webmention" href="{% url 'webmention-endpoint' %}">
```

If you omit these, IndieAuth login, Micropub posting, and incoming Webmentions will not work.

---

## Templates: Structure and Expectations

Themes provide templates under `templates/`. The exact structure is flexible, but some conventions exist.

### `blog/post.html`: the post dispatcher

The system renders all post types through `blog/post.html`. The default pattern is to branch on `post.kind` and `{% include %}` per-kind partials:

```html
{% extends 'base.html' %}

{% block content %}
  {% if post.kind == 'note' %}
    {% include 'blog/note.html' %}
  {% elif post.kind == 'article' %}
    {% include 'blog/article.html' %}
  {# ... etc #}
  {% endif %}
{% endblock %}
```

You are not required to use this pattern, but it keeps templates readable.

### Error templates

Error templates (`400.html`, `403.html`, `404.html`, `500.html`) receive only minimal context. Assume context processors may not run. Do not reference `settings`, `theme`, or `menu_items` in error templates without a fallback.

### Base template blocks

`base.html` should define at minimum:

- `{% block head %}` — for per-page `<head>` additions
- `{% block content %}` — for page body content

Additional blocks are up to you. The default theme also defines `{% block footer_extra %}`.

Example:

```html
{% extends "base.html" %}

{% block content %}
  <article>
    {{ page.html }}
  </article>
{% endblock %}
```

---

## Static Assets

Static assets live under `static/` inside your theme.

Use `theme_static` to reference them (it is auto-loaded — no `{% load %}` needed):

```html
<link rel="stylesheet" href="{% theme_static 'css/theme.css' %}">
<script src="{% theme_static 'js/theme.js' %}" defer></script>
```

Why this matters:

- It ensures the correct theme is used
- It avoids hard-coding paths
- It allows themes to be moved or renamed safely

---

## Progressive Enhancement

Themes should work well even when:

- JavaScript is unavailable
- Optional features are disabled
- Content is missing or incomplete

Aim for:

- Semantic HTML
- CSS-first layouts
- Enhancements layered on top, not required

---

## Common Mistakes to Avoid

- Using `settings.site_name` — the field is `settings.title`
- Relying on undocumented context variables
- Assuming a setting always exists — always guard with `|default`
- Hard-coding static paths — always use `theme_static`
- Using themes to implement features
- Assuming error templates have full context

If you find yourself needing logic, stop and reconsider the design.

---

## Testing Your Theme

Before sharing or publishing a theme:

- Test with no settings changed
- Test with extreme setting values
- Test missing content (no title, no author, no menu items)
- Test all post kinds: article, note, photo, activity, like, reply, repost, event, rsvp, checkin, bookmark
- Test with comments enabled and disabled
- Test with no site author configured
- Switch between themes to confirm isolation

A good theme fails quietly and predictably.

---

## Final Advice

A great theme:

- Looks good by default
- Is hard to break
- Makes few assumptions
- Respects user content

If you optimize for those goals, your theme will age well.
