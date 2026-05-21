const state = {
  selectedAreaId: null,
  selectedAreaName: "",
};

const elements = {
  username: document.querySelector("#username"),
  password: document.querySelector("#password"),
  loadAreasButton: document.querySelector("#load-areas-button"),
  areasList: document.querySelector("#areas-list"),
  selectedAreaLabel: document.querySelector("#selected-area-label"),
  reloadGridsButton: document.querySelector("#reload-grids-button"),
  message: document.querySelector("#message"),
  gridsBody: document.querySelector("#grids-body"),
};

function authHeaders(extraHeaders = {}) {
  const username = elements.username.value.trim();
  const password = elements.password.value;
  const token = btoa(`${username}:${password}`);

  return {
    Authorization: `Basic ${token}`,
    ...extraHeaders,
  };
}

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = type ? `message is-${type}` : "message";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  if (value === null || value === undefined) {
    return "";
  }
  const numberValue = Number(value);
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(2);
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch (error) {
    return { detail: text };
  }
}

function errorText(response, data) {
  if (data && data.detail) {
    return `${response.status} ${response.statusText}: ${data.detail}`;
  }
  if (data) {
    return `${response.status} ${response.statusText}: ${JSON.stringify(data)}`;
  }
  return `${response.status} ${response.statusText}`;
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  const data = await readJsonResponse(response);

  if (!response.ok) {
    throw new Error(errorText(response, data));
  }

  return data;
}

function renderAreas(areas) {
  if (!areas.length) {
    elements.areasList.textContent = "MapArea がありません。";
    return;
  }

  elements.areasList.innerHTML = areas
    .map(
      (area) => `
        <button
          class="area-button${area.id === state.selectedAreaId ? " is-selected" : ""}"
          type="button"
          data-area-id="${area.id}"
          data-area-name="${escapeHtml(area.name)}"
        >
          #${area.id} ${escapeHtml(area.name)}
        </button>
      `
    )
    .join("");
}

function renderEmptyGrids(message) {
  elements.gridsBody.innerHTML = `
    <tr>
      <td colspan="9">${escapeHtml(message)}</td>
    </tr>
  `;
}

function renderGrids(grids) {
  if (!grids.length) {
    renderEmptyGrids("GridCell がありません。");
    return;
  }

  elements.gridsBody.innerHTML = grids
    .map(
      (grid) => `
        <tr>
          <td>${grid.id}</td>
          <td>${grid.row_index}</td>
          <td>${grid.col_index}</td>
          <td>${formatNumber(grid.initial_score)}</td>
          <td>${formatNumber(grid.average_user_score)}</td>
          <td>${grid.rating_count}</td>
          <td>${formatNumber(grid.calculated_score)}</td>
          <td>
            <input
              class="score-input"
              type="number"
              min="1"
              max="10"
              value="5"
              aria-label="GridCell ${grid.id} score"
              data-score-for="${grid.id}"
            >
          </td>
          <td>
            <button class="rating-button" type="button" data-rate-grid="${grid.id}">
              採点
            </button>
          </td>
        </tr>
      `
    )
    .join("");
}

async function loadAreas() {
  setMessage("MapArea 一覧を取得しています。");
  elements.loadAreasButton.disabled = true;

  try {
    const data = await apiFetch("/api/maps/areas/");
    renderAreas(data.areas || []);
    setMessage("MapArea 一覧を取得しました。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.loadAreasButton.disabled = false;
  }
}

async function selectArea(areaId, areaName) {
  state.selectedAreaId = Number(areaId);
  state.selectedAreaName = areaName;
  elements.selectedAreaLabel.textContent = `選択中: #${areaId} ${areaName}`;
  elements.reloadGridsButton.disabled = false;

  document.querySelectorAll(".area-button").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      Number(button.dataset.areaId) === state.selectedAreaId
    );
  });

  await loadGrids();
}

async function loadGrids() {
  if (!state.selectedAreaId) {
    renderEmptyGrids("MapArea を選択してください。");
    return;
  }

  setMessage("GridCell 一覧を取得しています。");
  elements.reloadGridsButton.disabled = true;

  try {
    const data = await apiFetch(`/api/maps/areas/${state.selectedAreaId}/grids/`);
    renderGrids(data.grids || []);
    setMessage("GridCell 一覧を取得しました。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.reloadGridsButton.disabled = false;
  }
}

async function rateGrid(gridId) {
  const scoreInput = document.querySelector(`[data-score-for="${gridId}"]`);
  const score = Number(scoreInput.value);

  if (!Number.isInteger(score) || score < 1 || score > 10) {
    setMessage("score は 1 から 10 の整数で入力してください。", "error");
    return;
  }

  setMessage(`GridCell #${gridId} を採点しています。`);

  try {
    await apiFetch(`/api/maps/grids/${gridId}/ratings/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        score,
        comment: "demo page rating",
      }),
    });
    setMessage(`GridCell #${gridId} を採点しました。`, "success");
    await loadGrids();
  } catch (error) {
    setMessage(error.message, "error");
  }
}

elements.loadAreasButton.addEventListener("click", loadAreas);
elements.reloadGridsButton.addEventListener("click", loadGrids);

elements.areasList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-area-id]");
  if (!button) {
    return;
  }

  selectArea(button.dataset.areaId, button.dataset.areaName);
});

elements.gridsBody.addEventListener("click", (event) => {
  const button = event.target.closest("[data-rate-grid]");
  if (!button) {
    return;
  }

  rateGrid(button.dataset.rateGrid);
});
