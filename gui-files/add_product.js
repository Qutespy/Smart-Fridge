(function () {
  const openBtn = document.getElementById("open-add-product");
  const dialog = document.getElementById("add-product-dialog");
  const cancelBtn = document.getElementById("ap-cancel");
  const nameInput = document.getElementById("ap-name");
  const productIdInput = document.getElementById("ap-product-id");
  const suggestionsList = document.getElementById("ap-suggestions");
  const extraBlock = document.getElementById("ap-extra");
  const expInput = document.getElementById("ap-exp");
  const categorySelect = document.getElementById("ap-category");

  if (!openBtn || !dialog) return;

  const defaultDate = new Date();
  defaultDate.setDate(defaultDate.getDate() + 7);
  expInput.value = defaultDate.toISOString().slice(0, 10);

  openBtn.addEventListener("click", () => dialog.showModal());
  cancelBtn.addEventListener("click", () => dialog.close());

  let debounceTimer = null;
  nameInput.addEventListener("input", () => {
    productIdInput.value = "";
    extraBlock.hidden = false;
    clearTimeout(debounceTimer);
    const q = nameInput.value.trim();
    if (q.length < 2) {
      suggestionsList.innerHTML = "";
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/catalog/search?q=${encodeURIComponent(q)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        renderSuggestions(data.results || []);
      } catch (e) {
        console.error(e);
      }
    }, 300);
  });

  function renderSuggestions(items) {
    suggestionsList.innerHTML = "";
    items.slice(0, 8).forEach((p) => {
      const li = document.createElement("li");
      li.textContent = p.name;
      li.dataset.id = p.id;
      li.dataset.category = p.category || "other";
      li.dataset.shelfLife = p.default_shelf_life_days || "";
      li.addEventListener("click", () => selectSuggestion(p));
      suggestionsList.appendChild(li);
    });
  }

  function selectSuggestion(p) {
    nameInput.value = p.name;
    productIdInput.value = p.id;
    suggestionsList.innerHTML = "";
    extraBlock.hidden = true;
    if (p.category && categorySelect) categorySelect.value = p.category;
    if (p.default_shelf_life_days) {
      const d = new Date();
      d.setDate(d.getDate() + p.default_shelf_life_days);
      expInput.value = d.toISOString().slice(0, 10);
    }
  }

  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });
})();
