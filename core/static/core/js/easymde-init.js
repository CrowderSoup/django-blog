(function () {
  const instances = new WeakMap();

  const initEditor = (textarea) => {
    if (!window.EasyMDE || instances.has(textarea)) return;

    const editor = new EasyMDE({
      element: textarea,
      autoDownloadFontAwesome: true,
      spellChecker: false,
      status: false,
      minHeight: "300px",
      toolbar: [
        "bold",
        "italic",
        "heading",
        "|",
        "unordered-list",
        "ordered-list",
        "|",
        "link",
        "image",
        "code",
        "|",
        "preview",
        "side-by-side",
        "fullscreen",
        "|",
        "guide",
      ],
    });

    const syncTextarea = () => {
      textarea.value = editor.value();
    };

    syncTextarea();
    editor.codemirror.on("change", syncTextarea);

    instances.set(textarea, editor);

    const form = textarea.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        syncTextarea();
      });
      form.addEventListener("htmx:beforeRequest", () => {
        syncTextarea();
      });
    }
  };

  const initWithin = (root) => {
    root = root || document;
    root.querySelectorAll("textarea[data-easymde]").forEach(initEditor);
  };

  document.addEventListener("DOMContentLoaded", () => initWithin());
  document.addEventListener("htmx:afterSwap", (event) => {
    const target = event.detail?.target || event.target;
    if (!target || !(target instanceof Element)) return;
    initWithin(target);
  });
})();
