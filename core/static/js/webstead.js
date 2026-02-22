(() => {
  // Grab the visit ID from a meta tag
  const visitId = document.querySelector('meta[name="visit-id"]')?.content;
  if (!visitId) return;

  function sendBeacon() {
    navigator.sendBeacon(
      "/analytics/leave/",
      JSON.stringify({ visit_id: visitId, ts: Date.now() }),
    );
  }

  // Fire when the page is hidden or unloading
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") sendBeacon();
  });

  window.addEventListener("pagehide", () => {
    sendBeacon();
  });
})();

(() => {
  const existingBar = document.querySelector(".site-admin-bar");
  if (existingBar) {
    return;
  }

  const bindCloseOnClickOutside = (bar) => {
    if (!bar || document.body?.dataset.siteAdminBarCloseBound === "true") {
      return;
    }

    const menus = bar.querySelectorAll("details");
    if (!menus.length) {
      return;
    }

    document.body.dataset.siteAdminBarCloseBound = "true";
    document.addEventListener("click", (event) => {
      menus.forEach((menu) => {
        if (!menu.open) return;
        if (!menu.contains(event.target)) {
          menu.open = false;
        }
      });
    });
  };

  const url = document.body?.dataset.siteAdminBarUrl || "/admin/bar/";

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

      bindCloseOnClickOutside(document.querySelector(".site-admin-bar"));
    })
    .catch(() => {
      // Silent fail so the main site still loads if the admin bar endpoint is unavailable.
    });
})();
