(() => {
  async function parseGpxPoints(url) {
    const response = await fetch(url);
    if (!response.ok) return [];
    const text = await response.text();
    const xml = new DOMParser().parseFromString(text, "application/xml");
    if (xml.querySelector("parsererror")) return [];

    const points = Array.from(xml.querySelectorAll("trkpt, rtept"))
      .map((point) => {
        const lat = parseFloat(point.getAttribute("lat"));
        const lon = parseFloat(point.getAttribute("lon"));
        if (Number.isNaN(lat) || Number.isNaN(lon)) return null;
        return [lat, lon];
      })
      .filter(Boolean);

    return points;
  }

  function initMaps() {
    if (!window.L) return;

    const iconBase = "https://unpkg.com/leaflet@1.9.4/dist/images/";
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: `${iconBase}marker-icon-2x.png`,
      iconUrl: `${iconBase}marker-icon.png`,
      shadowUrl: `${iconBase}marker-shadow.png`,
    });

    document.querySelectorAll(".activity-map").forEach(async (el) => {
      const gpxUrl = el.dataset.gpxUrl;
      if (!gpxUrl) return;

      const map = L.map(el, { scrollWheelZoom: false });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      const points = await parseGpxPoints(gpxUrl);
      if (!points.length) {
        map.setView([0, 0], 2);
        return;
      }
      const line = L.polyline(points, {
        color: "#1d4ed8",
        weight: 4,
        opacity: 0.9,
      }).addTo(map);
      map.fitBounds(line.getBounds(), { padding: [20, 20] });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMaps);
  } else {
    initMaps();
  }
})();
