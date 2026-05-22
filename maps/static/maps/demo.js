const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  areasById: new Map(),
};

const elements = {
  username: document.querySelector("#username"),
  password: document.querySelector("#password"),
  loadAreasButton: document.querySelector("#load-areas-button"),
  createAreaForm: document.querySelector("#create-area-form"),
  createAreaButton: document.querySelector("#create-area-button"),
  areaName: document.querySelector("#area-name"),
  areaDescription: document.querySelector("#area-description"),
  areaNorth: document.querySelector("#area-north"),
  areaSouth: document.querySelector("#area-south"),
  areaEast: document.querySelector("#area-east"),
  areaWest: document.querySelector("#area-west"),
  areaGridSize: document.querySelector("#area-grid-size"),
  areaSource: document.querySelector("#area-source"),
  areasList: document.querySelector("#areas-list"),
  selectedAreaLabel: document.querySelector("#selected-area-label"),
  reloadGridsButton: document.querySelector("#reload-grids-button"),
  message: document.querySelector("#message"),
  mapImageUrl: document.querySelector("#map-image-url"),
  scoreMapRatio: document.querySelector("#score-map-ratio"),
  scoreMap: document.querySelector("#score-map"),
  gridsBody: document.querySelector("#grids-body"),
};

const FALLBACK_AREA_ASPECT_RATIO = 1.4;
const MIN_AREA_ASPECT_RATIO = 0.6;
const MAX_AREA_ASPECT_RATIO = 2.2;

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
  if (!Number.isFinite(numberValue)) {
    return "";
  }
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(2);
}

function scoreClass(score) {
  const numberScore = Number(score);
  if (!Number.isFinite(numberScore)) {
    return "score-low";
  }
  if (numberScore >= 8) {
    return "score-very-high";
  }
  if (numberScore >= 6) {
    return "score-high";
  }
  if (numberScore >= 3) {
    return "score-middle";
  }
  return "score-low";
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function mapAreaAspectRatio(area) {
  if (!area) {
    return FALLBACK_AREA_ASPECT_RATIO;
  }

  const width = Number(area.east) - Number(area.west);
  const height = Number(area.north) - Number(area.south);

  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return FALLBACK_AREA_ASPECT_RATIO;
  }

  return clamp(width / height, MIN_AREA_ASPECT_RATIO, MAX_AREA_ASPECT_RATIO);
}

function selectedArea() {
  return state.areasById.get(state.selectedAreaId) || null;
}

function applyScoreMapAspectRatio() {
  const ratio = mapAreaAspectRatio(selectedArea());
  elements.scoreMap.parentElement.style.setProperty(
    "--score-map-aspect-ratio",
    ratio.toFixed(3)
  );
  elements.scoreMapRatio.textContent = `area ratio ${ratio.toFixed(2)}`;
}

function cssUrlValue(value) {
  return `url("${value.replaceAll("\\", "\\\\").replaceAll('"', '\\"')}")`;
}

function applyScoreMapBackgroundImage() {
  const imageUrl = elements.mapImageUrl.value.trim();
  const stage = elements.scoreMap.parentElement;

  if (!imageUrl) {
    stage.classList.remove("has-map-image");
    stage.style.removeProperty("--score-map-image");
    return;
  }

  stage.style.setProperty("--score-map-image", cssUrlValue(imageUrl));
  stage.classList.add("has-map-image");
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
  state.areasById = new Map(areas.map((area) => [Number(area.id), area]));

  if (!areas.length) {
    elements.areasList.textContent = "メモグリッドがありません。";
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

function readAreaForm() {
  return {
    name: elements.areaName.value.trim(),
    description: elements.areaDescription.value.trim(),
    north: Number(elements.areaNorth.value),
    south: Number(elements.areaSouth.value),
    east: Number(elements.areaEast.value),
    west: Number(elements.areaWest.value),
    grid_size_meters: Number(elements.areaGridSize.value),
    source: elements.areaSource.value.trim(),
  };
}

function renderEmptyGrids(message) {
  applyScoreMapAspectRatio();
  elements.scoreMap.textContent = message;
  elements.scoreMap.style.setProperty("--score-map-cols", 1);
  elements.scoreMap.style.setProperty("--score-map-rows", 1);
  elements.scoreMap.parentElement.style.setProperty("--score-map-cols", 1);
  elements.gridsBody.innerHTML = `
    <tr>
      <td colspan="9">${escapeHtml(message)}</td>
    </tr>
  `;
}

function renderScoreMap(grids) {
  applyScoreMapAspectRatio();

  const positionedGrids = grids.filter((grid) => {
    return Number.isInteger(Number(grid.row_index)) && Number.isInteger(Number(grid.col_index));
  });

  if (!positionedGrids.length) {
    elements.scoreMap.textContent = "row_index / col_index を持つ GridCell がありません。";
    elements.scoreMap.style.setProperty("--score-map-cols", 1);
    elements.scoreMap.style.setProperty("--score-map-rows", 1);
    elements.scoreMap.parentElement.style.setProperty("--score-map-cols", 1);
    return;
  }

  const maxRow = Math.max(...positionedGrids.map((grid) => Number(grid.row_index)));
  const maxCol = Math.max(...positionedGrids.map((grid) => Number(grid.col_index)));
  elements.scoreMap.style.setProperty("--score-map-rows", maxRow + 1);
  elements.scoreMap.style.setProperty("--score-map-cols", maxCol + 1);
  elements.scoreMap.parentElement.style.setProperty("--score-map-cols", maxCol + 1);
  elements.scoreMap.innerHTML = positionedGrids
    .map((grid) => {
      const row = Number(grid.row_index) + 1;
      const col = Number(grid.col_index) + 1;
      const score = formatNumber(grid.calculated_score) || "0";
      const className = scoreClass(grid.calculated_score);

      return `
        <div
          class="score-cell ${className}"
          style="grid-row: ${row}; grid-column: ${col};"
          title="GridCell #${grid.id}: calculated_score ${escapeHtml(score)}"
        >
          <strong class="score-value">${escapeHtml(score)}</strong>
          <span class="score-meta">#${grid.id}</span>
          <span class="score-meta">row ${escapeHtml(grid.row_index)} / col ${escapeHtml(grid.col_index)}</span>
        </div>
      `;
    })
    .join("");
}

function renderGrids(grids) {
  if (!grids.length) {
    renderEmptyGrids("GridCell がありません。");
    return;
  }

  renderScoreMap(grids);
  elements.gridsBody.innerHTML = grids
    .map(
      (grid) => {
        const calculatedScore = formatNumber(grid.calculated_score);
        const className = scoreClass(grid.calculated_score);

        return `
        <tr>
          <td>${grid.id}</td>
          <td>${escapeHtml(grid.row_index)}</td>
          <td>${escapeHtml(grid.col_index)}</td>
          <td>${formatNumber(grid.initial_score)}</td>
          <td>${formatNumber(grid.average_user_score)}</td>
          <td>${grid.rating_count}</td>
          <td><span class="score-badge ${className}">${calculatedScore || "0"}</span></td>
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
      `;
      }
    )
    .join("");
}

async function loadAreas() {
  setMessage("メモグリッド一覧を取得しています。");
  elements.loadAreasButton.disabled = true;

  try {
    const data = await apiFetch("/api/maps/areas/");
    renderAreas(data.areas || []);
    setMessage("メモグリッド一覧を取得しました。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.loadAreasButton.disabled = false;
  }
}

async function createArea(event) {
  event.preventDefault();

  const payload = readAreaForm();
  if (!payload.name) {
    setMessage("name を入力してください。", "error");
    return;
  }

  setMessage("メモグリッドを作成しています。");
  elements.createAreaButton.disabled = true;

  try {
    const area = await apiFetch("/api/maps/areas/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    state.selectedAreaId = area.id;
    state.selectedAreaName = area.name;
    await loadAreas();
    await selectArea(area.id, area.name);
    setMessage(`メモグリッド #${area.id} を作成しました。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.createAreaButton.disabled = false;
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
    renderEmptyGrids("メモグリッドを選択してください。");
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

elements.createAreaForm.addEventListener("submit", createArea);
elements.loadAreasButton.addEventListener("click", loadAreas);
elements.reloadGridsButton.addEventListener("click", loadGrids);
elements.mapImageUrl.addEventListener("input", applyScoreMapBackgroundImage);

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

applyScoreMapBackgroundImage();
