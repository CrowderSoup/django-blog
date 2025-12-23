(() => {
  const existingBar = document.querySelector(".site-admin-bar");
  if (existingBar) {
    return;
  }

  const url =
    document.body?.dataset.siteAdminBarUrl || "/admin/bar/";

  fetch(url, { credentials: "same-origin", redirect: "manual" })
    .then((response) => {
      if (!response.ok || response.redirected) {
        return null;
      }
      return response.text();
    })
    .then((html) => {
      if (!html || !html.trim()) {
        return;
      }

      const container = document.createElement("div");
      container.innerHTML = html;

      const fragment = document.createDocumentFragment();
      while (container.firstChild) {
        fragment.appendChild(container.firstChild);
      }

      const firstChild = document.body.firstChild;
      if (firstChild) {
        document.body.insertBefore(fragment, firstChild);
      } else {
        document.body.appendChild(fragment);
      }

      const bar = document.querySelector(".site-admin-bar");
      if (bar) {
        const bodyBg = getComputedStyle(document.body).backgroundColor;
        const htmlBg =
          getComputedStyle(document.documentElement).backgroundColor;
        const resolvedBg =
          bodyBg && bodyBg !== "rgba(0, 0, 0, 0)" ? bodyBg : htmlBg;
        if (resolvedBg) {
          bar.style.setProperty("--site-admin-bar-bg", resolvedBg);
        }
      }
    })
    .catch(() => {
      // Silent fail so the main site still loads if the admin bar endpoint is unavailable.
    });
})();
