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
