(() => {
  function slugify(text) {
    return text
      .toLowerCase()
      .replace(/['"]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .replace(/-+/g, "-");
  }

  function extractSourceValue(source, kind) {
    const value = source.value.trim();
    if (!value) return "";
    if (kind === "url") {
      try {
        const parsed = new URL(value);
        const parts = parsed.pathname.split("/").filter(Boolean);
        const last = parts[parts.length - 1] || parsed.hostname || "";
        return last.replace(/\.git$/i, "");
      } catch (err) {
        const trimmed = value.replace(/\.git$/i, "");
        const pieces = trimmed.split("/").filter(Boolean);
        return pieces[pieces.length - 1] || trimmed;
      }
    }
    return value;
  }

  function initSlugField(slugField) {
    if (slugField.dataset.slugInit === "1") return;
    const sourceSelector = slugField.dataset.slugSource;
    if (!sourceSelector) return;
    const sourceField = document.querySelector(sourceSelector);
    if (!sourceField) return;
    slugField.dataset.slugInit = "1";

    const sourceKind = slugField.dataset.slugSourceKind || "";
    const hasManualValue = slugField.value.trim().length > 0;
    if (hasManualValue) {
      slugField.dataset.slugManual = "1";
    }

    function syncSlug() {
      if (slugField.dataset.slugManual === "1") return;
      const rawValue = extractSourceValue(sourceField, sourceKind);
      slugField.value = slugify(rawValue);
    }

    sourceField.addEventListener("input", syncSlug);
    slugField.addEventListener("input", () => {
      slugField.dataset.slugManual = slugField.value.trim().length ? "1" : "0";
      if (slugField.dataset.slugManual !== "1") {
        syncSlug();
      }
    });

    if (!hasManualValue) {
      syncSlug();
    }
  }

  function initSlugFields() {
    document
      .querySelectorAll("input[data-slug-source]")
      .forEach(initSlugField);
  }

  function bindInit() {
    initSlugFields();
    if (document.body) {
      document.body.addEventListener("htmx:afterSwap", initSlugFields);
      document.body.addEventListener("htmx:afterSettle", initSlugFields);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindInit);
  } else {
    bindInit();
  }
})();
