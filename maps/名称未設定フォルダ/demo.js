const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  selectedGridId: null,
  selectedGrid: null,
  areasById: new Map(),
  gridsById: new Map(),
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
  selectedShareAreaLabel: document.querySelector("#selected-share-area-label"),
  reloadGridsButton: document.querySelector("#reload-grids-button"),
  message: document.querySelector("#message"),
  loadSharesButton: document.querySelector("#load-shares"),
  addShareForm: document.querySelector("#add-share-form"),
  addShareButton: document.querySelector("#add-share"),
  shareUsername: document.querySelector("#share-username"),
  shareMessage: document.querySelector("#share-message"),
  sharesList: document.querySelector("#shares-list"),
  mapImageUrl: document.querySelector("#map-image-url"),
  scoreMapRatio: document.querySelector("#score-map-ratio"),
  scoreMap: document.querySelector("#score-map"),
  selectedGridLabel: document.querySelector("#selected-grid-label"),
  selectedGridRatingForm: document.querySelector("#selected-grid-rating-form"),
  selectedGridScore: document.querySelector("#selected-grid-score"),
  selectedGridRateButton: document.querySelector("#selected-grid-rate-button"),
  selectedGridMessage: document.querySelector("#selected-grid-message"),
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

function setShareMessage(text, type = "") {
  elements.shareMessage.textContent = text;
  elements.shareMessage.className = type
    ? `message share-message is-${type}`
    : "message share-message";
}

function setSelectedGridMessage(text, type = "") {
  elements.selectedGridMessage.textContent = text;
  elements.selectedGridMessage.className = type
    ? `message selected-grid-message is-${type}`
    : "message selected-grid-message";
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

function requireSelectedAreaForShares() {
  if (state.selectedAreaId) {
    return true;
  }

  setShareMessage("先にメモグリッドを選択してください。", "error");
  return false;
}

function renderAreas(areas) {
  state.areasById = new Map(areas.map((area) => [Number(area.id), area]));

  if (!areas.length) {
    elements.areasList.textContent = "メモグリッドがありません。";
    return;
  }

  elements.areasList.innerHTML = areas
    .map((area) => {
      const ownerLabel = area.is_owner
        ? "作成者: 自分"
        : `作成者: ${area.created_by_username || "不明"}`;
      const areaClasses = [
        "area-button",
        area.id === state.selectedAreaId ? "is-selected" : "",
        area.visibility === "shared" ? "is-shared" : "",
      ]
        .filter(Boolean)
        .join(" ");

      return `
        <button
          class="${areaClasses}"
          type="button"
          data-area-id="${area.id}"
          data-area-name="${escapeHtml(area.name)}"
        >
          <span class="area-button-title">#${area.id} ${escapeHtml(area.name)}</span>
          <span class="area-button-meta">
            ${escapeHtml(area.display_type || "メモグリッド")} / ${ownerLabel}
          </span>
        </button>
      `;
    })
    .join("");
}

function renderShares(shares) {
  if (!shares.length) {
    elements.sharesList.textContent = "共有相手はまだ登録されていません。";
    return;
  }

  elements.sharesList.innerHTML = shares
    .map((share) => {
      const username = share.user ? share.user.username : "";

      return `
        <div class="share-item">
          <div>
            <strong>${escapeHtml(username)}</strong>
            <span>share #${escapeHtml(share.id)}</span>
          </div>
          <button
            class="share-delete-button"
            type="button"
            data-delete-share="${share.id}"
          >
            共有を解除
          </button>
        </div>
      `;
    })
    .join("");
}

function clearSelectedGrid() {
  state.selectedGridId = null;
  state.selectedGrid = null;
  elements.selectedGridLabel.textContent = "GridCell を選択してください。";
  elements.selectedGridRateButton.disabled = true;
  setSelectedGridMessage("");
  document.querySelectorAll(".score-cell.is-selected").forEach((cell) => {
    cell.classList.remove("is-selected");
  });
}

function renderSelectedGrid() {
  const grid = state.selectedGrid;

  if (!grid) {
    clearSelectedGrid();
    return;
  }

  const gridSummary = [
    `選択中のマス #${grid.id}`,
    `縦 ${Number(grid.row_index) + 1}`,
    `横 ${Number(grid.col_index) + 1}`,
    `初期 ${formatNumber(grid.initial_score) || "0"}`,
    `平均 ${formatNumber(grid.average_user_score) || "0"}`,
    `件数 ${grid.rating_count}`,
    `現在のスコア ${formatNumber(grid.calculated_score) || "0"}`,
  ].join(" / ");
  elements.selectedGridLabel.innerHTML = `
    ${escapeHtml(gridSummary)}
    <br>
    <span>再採点すると点数が更新されます。</span>
  `;
  elements.selectedGridScore.value = "5";
  elements.selectedGridRateButton.disabled = false;
  setSelectedGridMessage("");
}

function highlightSelectedScoreCell() {
  document.querySelectorAll(".score-cell").forEach((cell) => {
    cell.classList.toggle(
      "is-selected",
      Number(cell.dataset.gridId) === state.selectedGridId
    );
  });
}

function selectGrid(gridId) {
  const normalizedGridId = Number(gridId);
  const grid = state.gridsById.get(normalizedGridId);

  if (!grid) {
    clearSelectedGrid();
    return;
  }

  state.selectedGridId = normalizedGridId;
  state.selectedGrid = grid;
  renderSelectedGrid();
  highlightSelectedScoreCell();
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
  state.gridsById = new Map();
  clearSelectedGrid();
  applyScoreMapAspectRatio();
  elements.scoreMap.textContent = message;
  elements.scoreMap.style.setProperty("--score-map-cols", 1);
  elements.scoreMap.style.setProperty("--score-map-rows", 1);
  elements.scoreMap.parentElement.style.setProperty("--score-map-cols", 1);
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
          role="button"
          tabindex="0"
          data-grid-id="${grid.id}"
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
  state.gridsById = new Map(grids.map((grid) => [Number(grid.id), grid]));

  if (!grids.length) {
    renderEmptyGrids("GridCell がありません。");
    return;
  }

  renderScoreMap(grids);
  if (state.selectedGridId && state.gridsById.has(state.selectedGridId)) {
    state.selectedGrid = state.gridsById.get(state.selectedGridId);
    renderSelectedGrid();
    highlightSelectedScoreCell();
  } else {
    clearSelectedGrid();
  }
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
  clearSelectedGrid();
  elements.selectedAreaLabel.textContent = `選択中: #${areaId} ${areaName}`;
  elements.selectedShareAreaLabel.textContent = `選択中: #${areaId} ${areaName}`;
  elements.reloadGridsButton.disabled = false;
  elements.loadSharesButton.disabled = false;
  elements.addShareButton.disabled = false;
  elements.sharesList.textContent = "共有相手はまだ読み込んでいません。";
  setShareMessage("");

  document.querySelectorAll(".area-button").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      Number(button.dataset.areaId) === state.selectedAreaId
    );
  });

  await loadGrids();
}

async function loadShares() {
  if (!requireSelectedAreaForShares()) {
    return;
  }

  setShareMessage("共有相手一覧を取得しています。");
  elements.loadSharesButton.disabled = true;

  try {
    const data = await apiFetch(`/api/maps/areas/${state.selectedAreaId}/shares/`);
    renderShares(data.shares || []);
    setShareMessage("共有相手一覧を取得しました。", "success");
  } catch (error) {
    setShareMessage(
      `${error.message} 共有相手管理はメモグリッドの作成者だけが利用できます。`,
      "error"
    );
  } finally {
    elements.loadSharesButton.disabled = false;
  }
}

async function addShare(event) {
  event.preventDefault();

  if (!requireSelectedAreaForShares()) {
    return;
  }

  const username = elements.shareUsername.value.trim();
  if (!username) {
    setShareMessage("共有相手 username を入力してください。", "error");
    return;
  }

  setShareMessage("共有相手を追加しています。");
  elements.addShareButton.disabled = true;

  try {
    await apiFetch(`/api/maps/areas/${state.selectedAreaId}/shares/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username }),
    });
    elements.shareUsername.value = "";
    await loadShares();
    setShareMessage(`共有相手 ${username} を追加しました。`, "success");
  } catch (error) {
    setShareMessage(
      `${error.message} 共有相手管理はメモグリッドの作成者だけが利用できます。`,
      "error"
    );
  } finally {
    elements.addShareButton.disabled = false;
  }
}

async function deleteShare(shareId) {
  if (!requireSelectedAreaForShares()) {
    return;
  }

  setShareMessage(`share #${shareId} の共有を解除しています。`);

  try {
    await apiFetch(`/api/maps/areas/${state.selectedAreaId}/shares/${shareId}/`, {
      method: "DELETE",
    });
    await loadShares();
    setShareMessage(`share #${shareId} の共有を解除しました。`, "success");
  } catch (error) {
    setShareMessage(
      `${error.message} 共有相手管理はメモグリッドの作成者だけが利用できます。`,
      "error"
    );
  }
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

function isValidScore(score) {
  if (!Number.isInteger(score) || score < 1 || score > 10) {
    return false;
  }
  return true;
}

async function submitRating(gridId, score, comment = "demo page rating") {
  setMessage(`GridCell #${gridId} を採点しています。`);

  await apiFetch(`/api/maps/grids/${gridId}/ratings/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      score,
      comment,
    }),
  });
  setMessage(`GridCell #${gridId} を採点しました。`, "success");
  await loadGrids();
}

async function rateSelectedGrid(event) {
  event.preventDefault();

  if (!state.selectedGridId) {
    setSelectedGridMessage("GridCell を選択してください。", "error");
    return;
  }

  const score = Number(elements.selectedGridScore.value);
  if (!isValidScore(score)) {
    setSelectedGridMessage("score は 1 から 10 の整数で入力してください。", "error");
    return;
  }

  elements.selectedGridRateButton.disabled = true;
  setSelectedGridMessage(`GridCell #${state.selectedGridId} を採点しています。`);

  try {
    await submitRating(state.selectedGridId, score);
    setSelectedGridMessage(
      `GridCell #${state.selectedGridId} を採点しました。`,
      "success"
    );
  } catch (error) {
    setSelectedGridMessage(error.message, "error");
  } finally {
    elements.selectedGridRateButton.disabled = !state.selectedGridId;
  }
}

elements.createAreaForm.addEventListener("submit", createArea);
elements.loadAreasButton.addEventListener("click", loadAreas);
elements.reloadGridsButton.addEventListener("click", loadGrids);
elements.loadSharesButton.addEventListener("click", loadShares);
elements.addShareForm.addEventListener("submit", addShare);
elements.selectedGridRatingForm.addEventListener("submit", rateSelectedGrid);
elements.mapImageUrl.addEventListener("input", applyScoreMapBackgroundImage);

elements.areasList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-area-id]");
  if (!button) {
    return;
  }

  selectArea(button.dataset.areaId, button.dataset.areaName);
});

elements.scoreMap.addEventListener("click", (event) => {
  const cell = event.target.closest("[data-grid-id]");
  if (!cell) {
    return;
  }

  selectGrid(cell.dataset.gridId);
});

elements.scoreMap.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  const cell = event.target.closest("[data-grid-id]");
  if (!cell) {
    return;
  }

  event.preventDefault();
  selectGrid(cell.dataset.gridId);
});

elements.sharesList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete-share]");
  if (!button) {
    return;
  }

  deleteShare(button.dataset.deleteShare);
});

applyScoreMapBackgroundImage();
