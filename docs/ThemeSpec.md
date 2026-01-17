# Theme Spec

## Files and directory structure

This is the directory structure and base set of files for a theme:

```
themes/
  └── <slug>/
      ├── theme.json
      ├── static/
      └── templates/
          ├── base.html
          ├── 500.html
          ├── blog/
          │   ├── post.html
          │   └── posts.html
          ├── core/
          │   ├── index.html
          │   └── page.html
          └── micropub/
              └── indieauth_login.html
```

`static/` and `templates/` are required. Subdirectories are optional but recommended based on the features the theme supports.

## `theme.json` (Theme Metadata)

`theme.json` lives at `themes/<slug>/theme.json` and must be a valid JSON object. It describes the theme for discovery, admin display, and template settings.

### Required fields

- `label` (string) or `name` (string): Human-friendly theme name used in the admin and templates. If both are present, `label` is preferred.

### Optional fields

- `slug` (string): If provided, it must slugify to a URL-safe lowercase value and must match the theme directory name.
- `version` (string): Theme version for display and installs.
- `author` (string): Theme author for display.
- `description` (string): Short description for display.
- `settings` (object): Schema for theme settings editable in admin (see below).
- Any extra keys: Exposed to templates as `theme.metadata`.

### Theme settings schema (`settings`)

`settings` is an object containing a `fields` object. Each field is defined by a field name and a field definition object.

#### Supported field definition keys

- `type`: One of `string`, `text`, `boolean`, `number`, `color`, `select`. Defaults to `string`.
- `default`: Any JSON value, used when no stored value exists.
- `choices`: Array of values. Required for `select` fields.
- `label`: Human-friendly label shown in the admin UI.
- `help`: Optional help text shown in the admin UI.

### Validation notes

- `theme.json` must exist and be valid JSON.
- If `slug` is provided, it must slugify and match the directory slug.
- `version` must be a string if present.
- If `settings` is present, it must be an object.
- If `settings` is present, `settings.fields` must be an object.

### Example

```json
{
  "label": "Cool Theme",
  "slug": "cool-theme",
  "author": "ACME",
  "version": "1.0.0",
  "description": "Blue gradients and serif type.",
  "settings": {
    "fields": {
      "accent": { "type": "color", "default": "#111111" },
      "layout": {
        "type": "select",
        "choices": ["wide", "narrow"],
        "default": "wide"
      }
    }
  }
}
```

## Theme Settings

Theme settings are defined in `theme.json` and exposed to templates when the theme is active.

### 1) Define settings in `theme.json`

Add a `settings.fields` object with per-field definitions. Defaults are optional but strongly recommended.

```json
{
  "label": "My Theme",
  "settings": {
    "fields": {
      "accent_color": {
        "type": "color",
        "label": "Accent color",
        "default": "#cc3f2e"
      },
      "max_width": {
        "type": "string",
        "label": "Layout max width",
        "default": "72rem",
        "help": "Used for the main content column."
      }
    }
  }
}
```

Supported field types: `string`, `text`, `boolean`, `number`, `color`, `select`. These are validated by the admin UI.

### 2) Save values in the admin

Active theme settings are edited in **Settings → Themes → Theme settings**. Saved values are stored per theme.

### 3) Read settings in templates

The `theme` context processor exposes a `theme.settings` dictionary that merges saved values with defaults from `theme.json`.

```html
<style>
  :root {
    --accent: {{ theme.settings.accent_color|default:"#cc3f2e" }};
    --max-width: {{ theme.settings.max_width|default:"72rem" }};
  }
</style>
```

Notes:

- If a setting has no `default`, use Django’s `|default` filter in templates.
- Template defaults should mirror `theme.json` defaults and are a fallback, not a replacement.
- Settings are only available when a theme is active.

## Template Tags

### `author` library

#### Purpose

Expose author h-card data in templates with sensible fallbacks.

#### Tag(s)

##### `author_hcard_name`

###### What it does

Returns a display name for an author, in this order:

1. the first named h-card associated with the passed-in user
2. `site_author_hcard` from context (if present)
3. `settings.site_author` h-card (if configured)
4. empty string

###### Usage

```html
{% load author %}

<p>By {% author_hcard_name user %}</p>
```

If you omit the user argument, only the context and settings fallbacks are used:

```html
{% load author %}

<p>By {% author_hcard_name %}</p>
```

### `theme` library

#### Purpose

Resolve a static asset URL for the active theme.

#### Tag(s)

##### `theme_static`

###### What it does

Builds a static URL using the active theme’s `static_prefix` (the theme’s static directory root). If no theme is active, it falls back to Django’s standard `static()` behavior.

###### Usage

```html
{% load theme %}

<link rel="stylesheet" href="{% theme_static 'css/theme.css' %}" />
<img src="{% theme_static 'images/logo.svg' %}" alt="Logo" />
```

###### Notes

- Accepts paths with or without a leading slash.
- If the theme prefix is already included in the path, it will not be double-prepended.
