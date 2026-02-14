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

    instances.set(textarea, editor);

    const form = textarea.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        textarea.value = editor.value();
      });
      form.addEventListener("htmx:beforeRequest", () => {
        textarea.value = editor.value();
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
