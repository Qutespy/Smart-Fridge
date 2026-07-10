(function () {
  const btnOpen = document.getElementById("ai-recipe-btn");
  const modal = document.getElementById("ai-recipe-modal");
  const btnSubmit = document.getElementById("ai-recipe-submit");
  const btnCancel = document.getElementById("ai-recipe-cancel");
  const result = document.getElementById("ai-recipe-result");
  let lastParams = null;
  let shownTitles = [];

  if (!btnOpen || !modal || !btnSubmit || !btnCancel || !result) return;

  btnOpen.addEventListener("click", () => modal.showModal());
  btnCancel.addEventListener("click", () => modal.close());

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.close();
  });

  btnSubmit.addEventListener("click", async () => {
    const form = document.getElementById("ai-recipe-form");
    const fd = new FormData(form);
    const params = {
      meal_type: fd.get("meal_type") || null,
      cuisine: fd.get("cuisine") || null,
      restrictions: fd.getAll("restrictions"),
    };
    lastParams = params;
    shownTitles = [];
    modal.close();
    await fetchRecipe(params);
  });

  async function fetchRecipe(params) {
    result.innerHTML =
      '<p class="ai-loading">⏳ ИИ готовит рецепт… это может занять до 30 секунд.</p>';
    try {
      const body = Object.assign({}, params, { exclude_titles: shownTitles });
      const resp = await fetch("/api/ai-recipes/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        const msg = err.detail || err.error || "Не удалось получить рецепт";
        result.innerHTML = `<p class="ai-error">⚠️ ${escapeHtml(msg)}</p>`;
        return;
      }
      const recipe = await resp.json();
      if (recipe && recipe.title) shownTitles.push(recipe.title);
      renderRecipe(recipe);
    } catch (e) {
      result.innerHTML = `<p class="ai-error">⚠️ Ошибка сети: ${escapeHtml(e.message)}</p>`;
    }
  }

  function renderRecipe(r) {
    const ingHtml = r.ingredients
      .map((i) => {
        const icon = i.available ? "🟢" : "🟡";
        const subs =
          i.substitutes && i.substitutes.length
            ? ` <small>(можно заменить: ${i.substitutes.map(escapeHtml).join(", ")})</small>`
            : "";
        const critical = i.critical ? "" : ` <em class="ai-optional">(необязательно)</em>`;
        return `<li>${icon} <strong>${escapeHtml(i.name)}</strong> — ${escapeHtml(i.amount)}${critical}${subs}</li>`;
      })
      .join("");
    const stepsHtml = r.steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("");

    result.innerHTML = `
      <article class="recipe-card">
        <h3>${escapeHtml(r.title)}</h3>
        <p>${escapeHtml(r.description)}</p>
        <p class="muted">⏱ ${r.cook_time_minutes} мин · 🍽 ${r.servings} порц. · ${escapeHtml(r.cuisine)} · ${escapeHtml(r.difficulty)}</p>
        <h4>Ингредиенты</h4>
        <ul class="ingredient-list">${ingHtml}</ul>
        <h4>Приготовление</h4>
        <ol class="ai-steps">${stepsHtml}</ol>
        ${r.notes ? `<p class="ai-notes"><em>${escapeHtml(r.notes)}</em></p>` : ""}
        <button id="ai-recipe-again" class="btn btn-dark">Ещё вариант</button>
      </article>
    `;
    const again = document.getElementById("ai-recipe-again");
    if (again) {
      again.addEventListener("click", () => {
        if (lastParams) fetchRecipe(lastParams);
      });
    }
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
