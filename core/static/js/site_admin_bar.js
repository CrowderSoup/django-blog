(() => {
  const existingBar = document.querySelector(".site-admin-bar");
  if (existingBar) {
    return;
  }

  const adminBarUrl = document.body?.dataset.siteAdminBarUrl || "/admin/bar/";
  const requestUrl = new URL(adminBarUrl, window.location.origin);
  requestUrl.searchParams.set("path", window.location.pathname);

  fetch(requestUrl.toString(), { credentials: "same-origin", redirect: "manual" })
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
    })
    .catch(() => {
      // Silent fail so the main site still loads if the admin bar endpoint is unavailable.
    });
})();
