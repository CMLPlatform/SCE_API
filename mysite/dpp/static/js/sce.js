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

// Clickable rows: <tr data-href="..."> opens the link, unless a link, button or checkbox cell was clicked.
document.querySelectorAll("tr[data-href]").forEach((row) => {
  row.addEventListener("click", (event) => {
    if (event.target.closest("a, button, input, label, form, .select-cell")) return;
    window.location = row.dataset.href;
  });
});

// Grouped selection table (see dpp/metadata_list.html), inside [data-grouped-table]:
// - <tbody data-group="ID"> is the head row of a group. Its [data-group-toggle] button
//   opens and closes <tbody id="ID">, which holds the rows of the group.
// - [data-select-all], [data-select-group] and [data-select-row] are checkboxes.
//   "Select all" and a group checkbox skip rows that the search hides.
// - [data-delete-selected] is enabled when one or more rows are selected, and
//   [data-selected-count] shows how many.
// - [data-expand-all] opens or closes all groups.
// - While the search box has text, the groups with a match open and the others hide.
document.querySelectorAll("[data-grouped-table]").forEach((root) => {
  const rowBoxes = [...root.querySelectorAll("[data-select-row]")];
  const selectAll = root.querySelector("[data-select-all]");
  const deleteButton = root.querySelector("[data-delete-selected]");
  const count = root.querySelector("[data-selected-count]");
  const expandAll = root.querySelector("[data-expand-all]");
  const search = root.querySelector("[data-table-filter]");
  const groups = [...root.querySelectorAll("tbody[data-group]")].map((head) => {
    const body = document.getElementById(head.dataset.group);
    return {
      head, body,
      toggle: head.querySelector("[data-group-toggle]"),
      box: head.querySelector("[data-select-group]"),
      rows: [...body.querySelectorAll("[data-select-row]")],
      open: false,
    };
  });
  const searching = () => Boolean(search && search.value.trim());
  const visible = (boxes) => boxes.filter((box) => !box.closest("tr").hidden);

  function setBox(box, boxes) {
    const checked = boxes.filter((b) => b.checked).length;
    box.checked = boxes.length > 0 && checked === boxes.length;
    box.indeterminate = checked > 0 && checked < boxes.length;
  }

  function update() {
    groups.forEach((g) => setBox(g.box, visible(g.rows)));
    setBox(selectAll, visible(rowBoxes));
    const selected = rowBoxes.filter((b) => b.checked).length;
    if (count) count.textContent = selected;
    if (deleteButton) deleteButton.disabled = selected === 0;
  }

  function show(g, open) {
    g.body.hidden = !open;
    g.toggle.setAttribute("aria-expanded", String(open));
  }

  function render() {
    groups.forEach((g) => {
      const matches = visible(g.rows).length > 0;
      g.head.hidden = searching() && !matches;
      show(g, searching() ? matches : g.open);
    });
    if (expandAll) {
      const allOpen = groups.every((g) => g.open);
      expandAll.setAttribute("aria-pressed", String(allOpen));
      expandAll.querySelector("span").textContent = allOpen ? "Collapse all" : "Expand all";
      expandAll.querySelector(".bi").className = `bi ${allOpen ? "bi-arrows-collapse" : "bi-arrows-expand"}`;
    }
    update();
  }

  groups.forEach((g) => {
    g.toggle.addEventListener("click", () => {
      if (searching()) return show(g, g.body.hidden); // Until the search changes
      g.open = !g.open;
      render();
    });
    g.box.addEventListener("change", () => {
      visible(g.rows).forEach((b) => { b.checked = g.box.checked; });
      update();
    });
  });
  rowBoxes.forEach((b) => b.addEventListener("change", update));
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      visible(rowBoxes).forEach((b) => { b.checked = selectAll.checked; });
      update();
    });
  }
  if (expandAll) {
    expandAll.addEventListener("click", () => {
      const open = !groups.every((g) => g.open);
      groups.forEach((g) => { g.open = open; });
      render();
    });
  }
  // Runs after the table search above, so the rows that match are already known
  if (search) search.addEventListener("input", render);
  render(); // The browser can keep checked boxes after "Back"
});

// Keep the selected tab when the page reloads (e.g. after a form post): uses the URL hash.
document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
  tab.addEventListener("shown.bs.tab", () => history.replaceState(null, "", tab.dataset.bsTarget));
});
if (window.location.hash) {
  const tab = document.querySelector(`[data-bs-toggle="tab"][data-bs-target="${window.location.hash}"]`);
  if (tab && window.bootstrap) bootstrap.Tab.getOrCreateInstance(tab).show();
}

// ---------------------------------------------------------------------------
// Form card: add and edit forms open in a dialog over the page, not in a pop-up
// window. After a save, the user stays on their page and the page shows the change.
//
// - A link to an add or edit page (/dpp/<model>/add/ or /dpp/<model>/<pk>/update/)
//   opens in the card. Add data-full-page to a link to open the page instead.
// - data-form-card-guide="text" on a link shows that text at the top of the card.
// - A "+" button next to a dropdown opens a second form in the same card. After the
//   save, the card goes back to the first form and selects the new item there.
// - The server sends the form only when the URL has _card=1 (see FormCardMixin),
//   and JSON {pk, name} after a valid save.
// ---------------------------------------------------------------------------
(() => {
  const card = document.getElementById("form-card");
  if (!card || !window.bootstrap) return;
  const modal = bootstrap.Modal.getOrCreateInstance(card);
  const body = card.querySelector(".form-card-body");
  const title = card.querySelector("#form-card-title");
  const returnNote = card.querySelector(".form-card-return");
  const guide = card.querySelector(".form-card-guide");
  const FORM_PATH = /^\/dpp\/[a-z]+\/(add|[^/]+\/update)\/$/;

  // One entry per open form: the inner form is last. Each entry keeps its own
  // content, so the outer form keeps what the user typed while the inner one is open.
  let stack = [];
  let reloadOnClose = false;

  function cardUrl(href) {
    const url = new URL(href, window.location.href);
    url.searchParams.delete("_popup");
    url.searchParams.delete("_to_field");
    url.searchParams.set("_card", "1");
    return url;
  }

  function show() {
    const entry = stack[stack.length - 1];
    body.replaceChildren(entry.content);
    title.textContent = entry.title;
    const outer = stack[stack.length - 2];
    returnNote.classList.toggle("d-none", !outer);
    returnNote.textContent = outer ? `After you save, you go back to: ${outer.title}` : "";
    guide.classList.toggle("d-none", !(stack.length === 1 && entry.guide));
    guide.querySelector(".form-card-guide-text").textContent = entry.guide || "";
    const first = body.querySelector("input:not([type=hidden]), select, textarea");
    if (first) first.focus();
  }

  function showError(entry, message, href) {
    entry.content = document.createElement("div");
    entry.content.innerHTML = '<div class="alert alert-danger" role="alert"></div>' +
      '<div class="d-flex justify-content-end gap-2"><a class="btn btn-outline-secondary" data-full-page>Open as a page</a>' +
      '<button type="button" class="btn btn-primary" data-card-cancel>Close</button></div>';
    entry.content.querySelector(".alert").textContent = message;
    entry.content.querySelector("a").href = href;
    show();
  }

  // Load or post `entry.url`, then show the form again or finish the entry.
  async function load(entry, options = {}) {
    let response;
    try {
      response = await fetch(entry.url, { credentials: "same-origin", ...options });
    } catch (error) {
      return showError(entry, "The form could not be loaded. Check your connection, then try again.", entry.pageUrl);
    }
    if (response.redirected && !new URL(response.url).searchParams.has("_card")) {
      window.location = response.url; // For example the log-in page, after the session ended
      return;
    }
    if (!response.ok) {
      return showError(entry, `The form could not be loaded (error ${response.status}).`, entry.pageUrl);
    }
    if ((response.headers.get("Content-Type") || "").includes("application/json")) {
      return finish(await response.json());
    }
    entry.content = document.createElement("div");
    entry.content.innerHTML = await response.text();
    const titled = entry.content.querySelector("[data-card-title]");
    entry.title = titled ? titled.dataset.cardTitle : "";
    show();
  }

  // The form at the top of the stack was saved.
  function finish(saved) {
    const entry = stack.pop();
    if (entry.select) {
      // Add the new item to the dropdown that has the "+" button, and select it.
      // Other dropdowns for the same kind of item get it too, without selecting it.
      const ref = entry.select.closest("[data-model-ref]")?.dataset.modelRef;
      const scope = entry.select.closest("form") || document;
      const targets = ref ? scope.querySelectorAll(`[data-model-ref="${ref}"] select`) : [entry.select];
      targets.forEach((select) => {
        if (![...select.options].some((o) => o.value === saved.pk)) {
          select.add(new Option(saved.name, saved.pk));
        }
      });
      const option = [...entry.select.options].find((o) => o.value === saved.pk);
      option.selected = true;
      entry.select.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      reloadOnClose = true; // Show the change on the page under the card
    }
    if (stack.length) show();
    else modal.hide();
  }

  function open(href, { select = null, guideText = "" } = {}) {
    const entry = { url: cardUrl(href), pageUrl: href, select, guide: guideText, title: "", content: null };
    if (!stack.length) {
      body.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading</span></div></div>';
      title.textContent = "";
      returnNote.classList.add("d-none");
      guide.classList.add("d-none");
    }
    stack.push(entry);
    modal.show();
    load(entry);
  }

  card.addEventListener("hidden.bs.modal", () => {
    stack = [];
    body.replaceChildren();
    if (reloadOnClose) window.location.reload();
  });

  // Save: send the form from the card, and stay in the card.
  body.addEventListener("submit", (event) => {
    const entry = stack[stack.length - 1];
    if (!entry) return;
    event.preventDefault();
    const button = event.target.querySelector("[type=submit]");
    if (button) button.disabled = true;
    load(entry, { method: "POST", body: new FormData(event.target) });
  });

  body.addEventListener("click", (event) => {
    if (event.target.closest("[data-card-cancel]")) {
      stack.pop();
      if (stack.length) show();
      else modal.hide();
      return;
    }
    const link = event.target.closest("a[href]");
    if (!link || link.hasAttribute("data-full-page")) return;
    if (link.matches("[data-card-link]")) {
      // Go to the next form in the same entry (for example: new product -> product model)
      event.preventDefault();
      const entry = stack[stack.length - 1];
      entry.url = cardUrl(link.href);
      entry.pageUrl = link.href;
      load(entry);
    }
  });

  // Links on the page, and "+" buttons both on the page and in the card.
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[href]");
    if (!link || link.hasAttribute("data-full-page")) return;
    if (link.matches(".related-widget-wrapper-link.add-related")) {
      event.preventDefault();
      const select = link.closest(".related-widget-wrapper").querySelector("select");
      open(link.href, { select });
      return;
    }
    if (card.contains(link)) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin === window.location.origin && FORM_PATH.test(url.pathname)) {
      event.preventDefault();
      open(link.href, { guideText: link.dataset.formCardGuide || "" });
    }
  });
})();
