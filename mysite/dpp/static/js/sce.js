// Small helpers shared by all app pages.

// Table search: <input data-table-filter="#table-id"> hides rows that don't match.
document.querySelectorAll("[data-table-filter]").forEach((input) => {
  const table = document.querySelector(input.dataset.tableFilter);
  if (!table) return;
  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();
    table.querySelectorAll("tbody tr[data-filterable]").forEach((row) => {
      row.hidden = query !== "" && !row.textContent.toLowerCase().includes(query);
    });
  });
});

// Clickable rows: <tr data-href="..."> opens the link, unless a link or button inside was clicked.
document.querySelectorAll("tr[data-href]").forEach((row) => {
  row.addEventListener("click", (event) => {
    if (event.target.closest("a, button, input, form")) return;
    window.location = row.dataset.href;
  });
});

// Keep the selected tab when the page reloads (e.g. after a form post): uses the URL hash.
document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
  tab.addEventListener("shown.bs.tab", () => history.replaceState(null, "", tab.dataset.bsTarget));
});
if (window.location.hash) {
  const tab = document.querySelector(`[data-bs-toggle="tab"][data-bs-target="${window.location.hash}"]`);
  if (tab && window.bootstrap) bootstrap.Tab.getOrCreateInstance(tab).show();
}
