const state = {
  selectedAreaId: null,
  selectedAreaName: "",
  selectedGridId: null,
  selectedGrid: null,
  selectedGridIds: new Set(),
  scoreMapViewMode: "fit",
  isDraggingSelection: false,
  dragStartPoint: null,
  dragCurrentPoint: null,
  suppressNextCellClick: false,
  areasById: new Map(),
  gridsById: new Map(),
  leafletMap: null,
  mapAreaRectangle: null,
  gridBoundaryLayer: null,
  mapGridRectanglesById: new Map(),
  isLeafletDragSelecting: false,
  leafletDragSelectStartLatLng: null,
  leafletDragSelectStartPoint: null,
  leafletDragSelectRectangle: null,
  suppressNextMapGridClick: false,
  extraZoomedAreaIds: new Set(),
};

const elements = {
  username: document.querySelector("#username"),
  password: document.querySelector("#password"),
  loadAreasButton: document.querySelector("#load-areas-button"),
  createAreaForm: document.querySelector("#create-area-form"),
  createAreaButton: document.querySelector("#create-area-button"),
  areaName: document.querySelector("#area-name"),
  areaDescription: document.querySelector("#area-description"),
  areaCenterLat: document.querySelector("#area-center-lat"),
  areaCenterLng: document.querySelector("#area-center-lng"),
  areaRows: document.querySelector("#area-rows"),
  areaCols: document.querySelector("#area-cols"),
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
  scoreMapViewModeInputs: document.querySelectorAll('input[name="score-map-view-mode"]'),
  scoreMapRatio: document.querySelector("#score-map-ratio"),
  scoreMap: document.querySelector("#score-map"),
  scoreMapWrap: document.querySelector(".score-map-wrap"),
  scoreMapStage: document.querySelector(".score-map-stage"),
  scoreSelectionRect: document.querySelector("#score-selection-rect"),
  mapPreview: document.querySelector("#map-preview"),
  mapPreviewStatus: document.querySelector("#map-preview-status"),
  selectedGridLabel: document.querySelector("#selected-grid-label"),
  selectedGridCount: document.querySelector("#selected-grid-count"),
  clearSelectedGridsButton: document.querySelector("#clear-selected-grids"),
  selectedGridsList: document.querySelector("#selected-grids-list"),
  individualRatingForm: document.querySelector("#individual-rating-form"),
  individualRatingSubmit: document.querySelector("#individual-rating-submit"),
  ratingModeInputs: document.querySelectorAll('input[name="multi-rating-mode"]'),
  sameScoreRatingForm: document.querySelector("#same-score-rating-form"),
  sameScoreInput: document.querySelector("#same-score-input"),
  sameScoreRatingSubmit: document.querySelector("#same-score-rating-submit"),
  selectedGridMessage: document.querySelector("#selected-grid-message"),
  selectedGridMessageText: document.querySelector("#selected-grid-message-text"),
  selectedGridLoadingSpinner: document.querySelector("#selected-grid-loading-spinner"),
};

const FALLBACK_AREA_ASPECT_RATIO = 1.4;
const MIN_AREA_ASPECT_RATIO = 0.6;
const MAX_AREA_ASPECT_RATIO = 2.2;
const DRAG_SELECT_THRESHOLD = 5;
const MAP_PREVIEW_EXTRA_ZOOM = 1;
const MAP_PREVIEW_MAX_ZOOM = 19;
const MAP_PREVIEW_EXTRA_ZOOM_MAX_LAT_DIFF = 0.02;
const MAP_PREVIEW_EXTRA_ZOOM_MAX_LNG_DIFF = 0.02;
const MAP_PREVIEW_SCORE_STYLES = {
  low: {
    color: "#4d6372",
    fillColor: "#dbe7ef",
    fillOpacity: 0.28,
  },
  middle: {
    color: "#9a6b00",
    fillColor: "#fff1b8",
    fillOpacity: 0.3,
  },
  high: {
    color: "#25733a",
    fillColor: "#bfe7c4",
    fillOpacity: 0.28,
  },
  veryHigh: {
    color: "#0d5f4e",
    fillColor: "#176f5c",
    fillOpacity: 0.24,
  },
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

function setShareMessage(text, type = "") {
  elements.shareMessage.textContent = text;
  elements.shareMessage.className = type
    ? `message share-message is-${type}`
    : "message share-message";
}

function setSelectedGridMessage(text, type = "", isLoading = false) {
  elements.selectedGridMessageText.textContent = text;
  elements.selectedGridLoadingSpinner.hidden = !isLoading;
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

function scoreLevel(score) {
  const numberScore = Number(score);
  if (!Number.isFinite(numberScore)) {
    return "low";
  }
  if (numberScore >= 8) {
    return "veryHigh";
  }
  if (numberScore >= 6) {
    return "high";
  }
  if (numberScore >= 3) {
    return "middle";
  }
  return "low";
}

function scoreClass(score) {
  const classes = {
    low: "score-low",
    middle: "score-middle",
    high: "score-high",
    veryHigh: "score-very-high",
  };
  return classes[scoreLevel(score)];
}

function mapPreviewScoreStyle(score) {
  return MAP_PREVIEW_SCORE_STYLES[scoreLevel(score)];
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

function leafletAvailable() {
  return typeof window.L !== "undefined";
}

function mapAreaBounds(area) {
  const north = Number(area.north);
  const south = Number(area.south);
  const east = Number(area.east);
  const west = Number(area.west);

  if (
    !Number.isFinite(north) ||
    !Number.isFinite(south) ||
    !Number.isFinite(east) ||
    !Number.isFinite(west) ||
    north <= south ||
    east <= west
  ) {
    return null;
  }

  return [
    [south, west],
    [north, east],
  ];
}

function gridCellBounds(grid) {
  return mapAreaBounds(grid);
}

function gridCellLatLngBounds(grid) {
  const bounds = gridCellBounds(grid);
  if (!bounds || !leafletAvailable()) {
    return null;
  }
  return window.L.latLngBounds(bounds);
}

function shouldApplyExtraMapPreviewZoom(area) {
  const latDiff = Math.abs(Number(area.north) - Number(area.south));
  const lngDiff = Math.abs(Number(area.east) - Number(area.west));

  if (!Number.isFinite(latDiff) || !Number.isFinite(lngDiff)) {
    return false;
  }

  return (
    latDiff <= MAP_PREVIEW_EXTRA_ZOOM_MAX_LAT_DIFF &&
    lngDiff <= MAP_PREVIEW_EXTRA_ZOOM_MAX_LNG_DIFF
  );
}

function applyExtraMapPreviewZoom(area) {
  const areaId = Number(area.id);
  if (state.extraZoomedAreaIds.has(areaId)) {
    return;
  }
  if (!shouldApplyExtraMapPreviewZoom(area)) {
    return;
  }

  const currentZoom = state.leafletMap.getZoom();
  if (!Number.isFinite(currentZoom)) {
    return;
  }

  state.leafletMap.setZoom(
    Math.min(currentZoom + MAP_PREVIEW_EXTRA_ZOOM, MAP_PREVIEW_MAX_ZOOM)
  );
  state.extraZoomedAreaIds.add(areaId);
}

function initMapPreview() {
  if (state.leafletMap || !elements.mapPreview) {
    return;
  }

  if (!leafletAvailable()) {
    elements.mapPreviewStatus.textContent = "Leaflet を読み込めませんでした。";
    return;
  }

  state.leafletMap = window.L.map(elements.mapPreview, {
    scrollWheelZoom: false,
    boxZoom: false,
  }).setView([35.69, 139.7], 11);

  window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(state.leafletMap);

  state.leafletMap.on("mousedown", startLeafletDragSelection);
  state.leafletMap.on("mousemove", updateLeafletDragSelection);
  state.leafletMap.on("mouseup", finishLeafletDragSelection);
}

function clearMapGridBoundaries() {
  cancelLeafletDragSelection();
  if (state.gridBoundaryLayer) {
    state.gridBoundaryLayer.clearLayers();
  }
  state.mapGridRectanglesById.clear();
}

function mapGridBoundaryLayer() {
  if (!state.leafletMap) {
    return null;
  }
  if (!state.gridBoundaryLayer) {
    state.gridBoundaryLayer = window.L.layerGroup().addTo(state.leafletMap);
  }
  return state.gridBoundaryLayer;
}

function updateMapGridBoundaries(grids) {
  clearMapGridBoundaries();

  if (!grids.length) {
    return;
  }

  initMapPreview();
  if (!state.leafletMap) {
    return;
  }

  const boundaryLayer = mapGridBoundaryLayer();
  if (!boundaryLayer) {
    return;
  }

  grids.forEach((grid) => {
    const bounds = gridCellBounds(grid);
    if (!bounds) {
      return;
    }
    const style = mapPreviewScoreStyle(grid.calculated_score);
    const gridId = Number(grid.id);

    const rectangle = window.L.rectangle(bounds, {
      color: style.color,
      weight: 1,
      opacity: 0.45,
      fillColor: style.fillColor,
      fillOpacity: style.fillOpacity,
      interactive: true,
      className: "map-preview-grid-boundary",
    });

    rectangle.on("click", () => {
      if (state.suppressNextMapGridClick) {
        state.suppressNextMapGridClick = false;
        return;
      }

      toggleGridSelection(gridId);
    });
    rectangle.addTo(boundaryLayer);
    state.mapGridRectanglesById.set(gridId, rectangle);
  });

  highlightSelectedMapGridBoundaries();

  if (state.mapAreaRectangle) {
    state.mapAreaRectangle.bringToFront();
  }
}

function updateMapPreview() {
  if (!elements.mapPreviewStatus) {
    return;
  }

  const area = selectedArea();
  if (!area) {
    clearMapAreaPreview();
    elements.mapPreviewStatus.textContent = "MapArea を選択してください。";
    return;
  }

  const bounds = mapAreaBounds(area);
  if (!bounds) {
    clearMapAreaPreview();
    elements.mapPreviewStatus.textContent = "MapArea の範囲を地図表示できません。";
    return;
  }

  initMapPreview();
  if (!state.leafletMap) {
    return;
  }

  if (state.mapAreaRectangle) {
    state.mapAreaRectangle.remove();
  }

  state.mapAreaRectangle = window.L.rectangle(bounds, {
    color: "#176f5c",
    weight: 2,
    fill: false,
  }).addTo(state.leafletMap);
  state.leafletMap.fitBounds(bounds, { padding: [20, 20] });
  applyExtraMapPreviewZoom(area);
  elements.mapPreviewStatus.textContent = `選択中 MapArea: #${area.id} ${area.name}`;

  window.setTimeout(() => {
    state.leafletMap.invalidateSize();
  }, 0);
}

function clearMapAreaPreview() {
  if (state.mapAreaRectangle) {
    state.mapAreaRectangle.remove();
    state.mapAreaRectangle = null;
  }

  clearMapGridBoundaries();

  if (elements.mapPreviewStatus) {
    elements.mapPreviewStatus.textContent = "MapArea を選択してください。";
  }
}

function setLeafletDraggingEnabled(isEnabled) {
  if (!state.leafletMap || !state.leafletMap.dragging) {
    return;
  }

  if (isEnabled) {
    state.leafletMap.dragging.enable();
    return;
  }

  state.leafletMap.dragging.disable();
}

function clearLeafletDragSelectionRectangle() {
  if (!state.leafletDragSelectRectangle) {
    return;
  }

  state.leafletDragSelectRectangle.remove();
  state.leafletDragSelectRectangle = null;
}

function cancelLeafletDragSelection() {
  if (state.isLeafletDragSelecting) {
    setLeafletDraggingEnabled(true);
  }

  state.isLeafletDragSelecting = false;
  state.leafletDragSelectStartLatLng = null;
  state.leafletDragSelectStartPoint = null;
  clearLeafletDragSelectionRectangle();

  if (elements.mapPreview) {
    elements.mapPreview.classList.remove("is-leaflet-drag-selecting");
  }
}

function leafletDragDistance(currentLatLng) {
  if (!state.leafletMap || !state.leafletDragSelectStartPoint || !currentLatLng) {
    return 0;
  }

  const currentPoint = state.leafletMap.latLngToContainerPoint(currentLatLng);
  const xDistance = currentPoint.x - state.leafletDragSelectStartPoint.x;
  const yDistance = currentPoint.y - state.leafletDragSelectStartPoint.y;

  return Math.hypot(xDistance, yDistance);
}

function leafletSelectionBounds(startLatLng, currentLatLng) {
  if (!startLatLng || !currentLatLng || !leafletAvailable()) {
    return null;
  }

  return window.L.latLngBounds(startLatLng, currentLatLng);
}

function updateLeafletDragSelectionRectangle(bounds) {
  if (!state.leafletMap || !bounds) {
    return;
  }

  if (!state.leafletDragSelectRectangle) {
    state.leafletDragSelectRectangle = window.L.rectangle(bounds, {
      color: "#176f5c",
      weight: 2,
      opacity: 0.9,
      dashArray: "4 4",
      fillColor: "#176f5c",
      fillOpacity: 0.12,
      interactive: false,
      className: "map-preview-drag-selection",
    }).addTo(state.leafletMap);
    return;
  }

  state.leafletDragSelectRectangle.setBounds(bounds);
  state.leafletDragSelectRectangle.bringToFront();
}

function selectMapGridCellsInBounds(selectionBounds) {
  if (!selectionBounds) {
    return 0;
  }

  let selectedCount = 0;
  let latestSelectedGrid = null;

  state.gridsById.forEach((grid, gridId) => {
    const bounds = gridCellLatLngBounds(grid);
    if (!bounds || !selectionBounds.intersects(bounds)) {
      return;
    }

    if (!state.selectedGridIds.has(gridId)) {
      selectedCount += 1;
    }
    state.selectedGridIds.add(gridId);
    latestSelectedGrid = grid;
  });

  if (latestSelectedGrid) {
    state.selectedGridId = Number(latestSelectedGrid.id);
    state.selectedGrid = latestSelectedGrid;
  }

  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();

  return selectedCount;
}

function startLeafletDragSelection(event) {
  if (
    !event.originalEvent.shiftKey ||
    !state.leafletMap ||
    !event.latlng ||
    !state.gridsById.size
  ) {
    return;
  }

  event.originalEvent.preventDefault();
  state.isLeafletDragSelecting = true;
  state.leafletDragSelectStartLatLng = event.latlng;
  state.leafletDragSelectStartPoint = state.leafletMap.latLngToContainerPoint(
    event.latlng
  );
  elements.mapPreview.classList.add("is-leaflet-drag-selecting");
  setLeafletDraggingEnabled(false);
}

function updateLeafletDragSelection(event) {
  if (!state.isLeafletDragSelecting || !event.latlng) {
    return;
  }

  event.originalEvent.preventDefault();
  const bounds = leafletSelectionBounds(state.leafletDragSelectStartLatLng, event.latlng);
  if (leafletDragDistance(event.latlng) < DRAG_SELECT_THRESHOLD) {
    clearLeafletDragSelectionRectangle();
    return;
  }

  updateLeafletDragSelectionRectangle(bounds);
}

function finishLeafletDragSelection(event) {
  if (!state.isLeafletDragSelecting) {
    return;
  }

  event.originalEvent.preventDefault();
  const bounds = leafletSelectionBounds(state.leafletDragSelectStartLatLng, event.latlng);
  const distance = leafletDragDistance(event.latlng);

  cancelLeafletDragSelection();

  if (distance < DRAG_SELECT_THRESHOLD || !bounds) {
    return;
  }

  selectMapGridCellsInBounds(bounds);
  state.suppressNextMapGridClick = true;
  window.setTimeout(() => {
    state.suppressNextMapGridClick = false;
  }, 0);
}

function applyScoreMapAspectRatio() {
  const ratio = mapAreaAspectRatio(selectedArea());
  elements.scoreMapStage.style.setProperty(
    "--score-map-aspect-ratio",
    ratio.toFixed(3)
  );
  elements.scoreMapRatio.textContent = `area ratio ${ratio.toFixed(2)}`;
}

function readScoreMapViewMode() {
  const checkedInput = document.querySelector(
    'input[name="score-map-view-mode"]:checked'
  );
  return checkedInput ? checkedInput.value : "fit";
}

function applyScoreMapViewMode() {
  const mode = state.scoreMapViewMode;
  elements.scoreMapWrap.classList.toggle("is-fit", mode === "fit");
  elements.scoreMapWrap.classList.toggle("is-detail", mode === "detail");
  elements.scoreMapStage.classList.toggle("is-fit", mode === "fit");
  elements.scoreMapStage.classList.toggle("is-detail", mode === "detail");
}

function applyScoreMapDensity(rowCount, colCount) {
  const maxSide = Math.max(rowCount, colCount);
  const cellCount = rowCount * colCount;
  const densityClasses = [
    "is-density-normal",
    "is-density-dense",
    "is-density-crowded",
  ];

  elements.scoreMapStage.classList.remove(...densityClasses);

  if (maxSide >= 12 || cellCount >= 96) {
    elements.scoreMapStage.classList.add("is-density-crowded");
    return;
  }
  if (maxSide >= 7 || cellCount >= 36) {
    elements.scoreMapStage.classList.add("is-density-dense");
    return;
  }

  elements.scoreMapStage.classList.add("is-density-normal");
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
      const deleteButton = area.is_owner
        ? `
          <button
            class="area-delete-button"
            type="button"
            data-delete-area-id="${area.id}"
            data-delete-area-name="${escapeHtml(area.name)}"
          >
            削除
          </button>
        `
        : "";

      return `
        <div class="area-item">
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
          ${deleteButton}
        </div>
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

function selectedGrids() {
  return Array.from(state.selectedGridIds)
    .map((gridId) => state.gridsById.get(gridId))
    .filter(Boolean)
    .sort((a, b) => {
      if (a.row_index !== b.row_index) {
        return a.row_index - b.row_index;
      }
      return a.col_index - b.col_index;
    });
}

function pruneMissingSelectedGrids() {
  state.selectedGridIds = new Set(
    Array.from(state.selectedGridIds).filter((gridId) => state.gridsById.has(gridId))
  );
}

function clearSelectedGrids() {
  state.selectedGridId = null;
  state.selectedGrid = null;
  state.selectedGridIds.clear();
  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();
}

function removeSelectedGrid(gridId) {
  const normalizedGridId = Number(gridId);
  state.selectedGridIds.delete(normalizedGridId);
  if (state.selectedGridId === normalizedGridId) {
    state.selectedGridId = null;
    state.selectedGrid = null;
  }
  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();
}

function renderSelectedGrids() {
  const grids = selectedGrids();

  if (!grids.length) {
    elements.selectedGridLabel.textContent = "GridCell を選択してください。";
    elements.selectedGridCount.textContent = "選択数: 0";
    elements.selectedGridsList.textContent = "GridCell を選択してください。";
    elements.clearSelectedGridsButton.disabled = true;
    elements.individualRatingSubmit.disabled = true;
    elements.sameScoreRatingSubmit.disabled = true;
    setSelectedGridMessage("");
    return;
  }

  const latestGrid = state.selectedGrid || grids[grids.length - 1];
  const latestSummary = [
    `直近の選択 #${latestGrid.id}`,
    `縦 ${Number(latestGrid.row_index) + 1}`,
    `横 ${Number(latestGrid.col_index) + 1}`,
    `現在のスコア ${formatNumber(latestGrid.calculated_score) || "0"}`,
  ].join(" / ");
  elements.selectedGridLabel.textContent = latestSummary;
  elements.selectedGridCount.textContent = `選択数: ${grids.length}`;
  elements.clearSelectedGridsButton.disabled = false;
  elements.individualRatingSubmit.disabled = false;
  elements.sameScoreRatingSubmit.disabled = false;
  elements.selectedGridsList.innerHTML = grids
    .map((grid) => {
      const score = formatNumber(grid.calculated_score) || "0";
      return `
        <div class="selected-grid-item">
          <div class="selected-grid-item-summary">
            <strong>#${grid.id}</strong>
            <span>縦 ${Number(grid.row_index) + 1} / 横 ${Number(grid.col_index) + 1}</span>
            <span>現在のスコア ${escapeHtml(score)}</span>
          </div>
          <label>
            score
            <input
              type="number"
              min="1"
              max="10"
              value="5"
              data-individual-score-for="${grid.id}"
            >
          </label>
          <button type="button" data-remove-selected-grid="${grid.id}">
            選択解除
          </button>
        </div>
      `;
    })
    .join("");
  setSelectedGridMessage("");
}

function highlightSelectedScoreCells() {
  document.querySelectorAll(".score-cell").forEach((cell) => {
    cell.classList.toggle(
      "is-selected",
      state.selectedGridIds.has(Number(cell.dataset.gridId))
    );
  });
}

function highlightSelectedMapGridBoundaries() {
  state.mapGridRectanglesById.forEach((rectangle, gridId) => {
    const grid = state.gridsById.get(gridId);
    if (!grid) {
      return;
    }

    const style = mapPreviewScoreStyle(grid.calculated_score);
    const isSelected = state.selectedGridIds.has(gridId);

    rectangle.setStyle({
      color: isSelected ? "#176f5c" : style.color,
      weight: isSelected ? 3 : 1,
      opacity: isSelected ? 0.95 : 0.45,
      fillColor: style.fillColor,
      fillOpacity: isSelected
        ? Math.min(style.fillOpacity + 0.18, 0.55)
        : style.fillOpacity,
    });

    if (isSelected) {
      rectangle.bringToFront();
    }
  });

  if (state.mapAreaRectangle) {
    state.mapAreaRectangle.bringToFront();
  }
}

function toggleGridSelection(gridId) {
  const normalizedGridId = Number(gridId);
  const grid = state.gridsById.get(normalizedGridId);

  if (!grid) {
    removeSelectedGrid(normalizedGridId);
    return;
  }

  if (state.selectedGridIds.has(normalizedGridId)) {
    removeSelectedGrid(normalizedGridId);
    return;
  }

  state.selectedGridIds.add(normalizedGridId);
  state.selectedGridId = normalizedGridId;
  state.selectedGrid = grid;
  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();
}

function stagePointFromEvent(event) {
  const stageRect = elements.scoreMapStage.getBoundingClientRect();
  return {
    x: event.clientX - stageRect.left,
    y: event.clientY - stageRect.top,
  };
}

function selectionRectFromPoints(startPoint, endPoint) {
  const left = Math.min(startPoint.x, endPoint.x);
  const top = Math.min(startPoint.y, endPoint.y);
  const width = Math.abs(endPoint.x - startPoint.x);
  const height = Math.abs(endPoint.y - startPoint.y);

  return {
    left,
    top,
    right: left + width,
    bottom: top + height,
    width,
    height,
  };
}

function dragDistance() {
  if (!state.dragStartPoint || !state.dragCurrentPoint) {
    return 0;
  }

  const xDistance = state.dragCurrentPoint.x - state.dragStartPoint.x;
  const yDistance = state.dragCurrentPoint.y - state.dragStartPoint.y;
  return Math.hypot(xDistance, yDistance);
}

function renderSelectionRect() {
  if (!state.dragStartPoint || !state.dragCurrentPoint) {
    return;
  }

  const rect = selectionRectFromPoints(state.dragStartPoint, state.dragCurrentPoint);
  elements.scoreSelectionRect.hidden = false;
  elements.scoreSelectionRect.style.left = `${rect.left}px`;
  elements.scoreSelectionRect.style.top = `${rect.top}px`;
  elements.scoreSelectionRect.style.width = `${rect.width}px`;
  elements.scoreSelectionRect.style.height = `${rect.height}px`;
}

function hideSelectionRect() {
  elements.scoreSelectionRect.hidden = true;
  elements.scoreSelectionRect.style.removeProperty("left");
  elements.scoreSelectionRect.style.removeProperty("top");
  elements.scoreSelectionRect.style.removeProperty("width");
  elements.scoreSelectionRect.style.removeProperty("height");
}

function cellRectIntersectsSelection(cellRect, selectionRect) {
  return !(
    cellRect.right < selectionRect.left ||
    cellRect.left > selectionRect.right ||
    cellRect.bottom < selectionRect.top ||
    cellRect.top > selectionRect.bottom
  );
}

function stageRelativeRect(element) {
  const stageRect = elements.scoreMapStage.getBoundingClientRect();
  const elementRect = element.getBoundingClientRect();

  return {
    left: elementRect.left - stageRect.left,
    top: elementRect.top - stageRect.top,
    right: elementRect.right - stageRect.left,
    bottom: elementRect.bottom - stageRect.top,
  };
}

function selectGridsInRect(selectionRect) {
  const selectedCells = Array.from(
    elements.scoreMap.querySelectorAll(".score-cell[data-grid-id]")
  ).filter((cell) => {
    return cellRectIntersectsSelection(stageRelativeRect(cell), selectionRect);
  });

  if (!selectedCells.length) {
    return;
  }

  selectedCells.forEach((cell) => {
    state.selectedGridIds.add(Number(cell.dataset.gridId));
  });

  const latestCell = selectedCells[selectedCells.length - 1];
  const latestGridId = Number(latestCell.dataset.gridId);
  state.selectedGridId = latestGridId;
  state.selectedGrid = state.gridsById.get(latestGridId) || null;
  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();
}

function canStartDragSelection(event) {
  if (event.button !== 0 || !state.selectedAreaId) {
    return false;
  }
  if (!elements.scoreMap.querySelector(".score-cell[data-grid-id]")) {
    return false;
  }
  return !event.target.closest("input, button, textarea, select, label");
}

function startDragSelection(event) {
  if (!canStartDragSelection(event)) {
    return;
  }

  state.isDraggingSelection = true;
  state.dragStartPoint = stagePointFromEvent(event);
  state.dragCurrentPoint = state.dragStartPoint;
  state.suppressNextCellClick = false;
  elements.scoreMapStage.classList.add("is-dragging-selection");
  if (elements.scoreMapStage.setPointerCapture) {
    elements.scoreMapStage.setPointerCapture(event.pointerId);
  }
  hideSelectionRect();
}

function updateDragSelection(event) {
  if (!state.isDraggingSelection) {
    return;
  }

  state.dragCurrentPoint = stagePointFromEvent(event);
  if (dragDistance() >= DRAG_SELECT_THRESHOLD) {
    event.preventDefault();
    renderSelectionRect();
  }
}

function finishDragSelection(event) {
  if (!state.isDraggingSelection) {
    return;
  }

  state.dragCurrentPoint = stagePointFromEvent(event);
  const shouldSelectRange = dragDistance() >= DRAG_SELECT_THRESHOLD;
  if (
    elements.scoreMapStage.releasePointerCapture &&
    elements.scoreMapStage.hasPointerCapture(event.pointerId)
  ) {
    elements.scoreMapStage.releasePointerCapture(event.pointerId);
  }
  elements.scoreMapStage.classList.remove("is-dragging-selection");

  if (shouldSelectRange) {
    state.suppressNextCellClick = true;
    selectGridsInRect(selectionRectFromPoints(state.dragStartPoint, state.dragCurrentPoint));
    window.setTimeout(() => {
      state.suppressNextCellClick = false;
    }, 0);
  }

  state.isDraggingSelection = false;
  state.dragStartPoint = null;
  state.dragCurrentPoint = null;
  hideSelectionRect();
}

function cancelDragSelection() {
  state.isDraggingSelection = false;
  state.dragStartPoint = null;
  state.dragCurrentPoint = null;
  elements.scoreMapStage.classList.remove("is-dragging-selection");
  hideSelectionRect();
}

function readAreaForm() {
  return {
    name: elements.areaName.value.trim(),
    description: elements.areaDescription.value.trim(),
    center_lat: Number(elements.areaCenterLat.value),
    center_lng: Number(elements.areaCenterLng.value),
    grid_size_meters: Number(elements.areaGridSize.value),
    rows: parseInt(elements.areaRows.value, 10),
    cols: parseInt(elements.areaCols.value, 10),
    source: elements.areaSource.value.trim(),
  };
}

function renderEmptyGrids(message) {
  cancelDragSelection();
  state.gridsById = new Map();
  clearMapGridBoundaries();
  clearSelectedGrids();
  applyScoreMapAspectRatio();
  elements.scoreMap.textContent = message;
  elements.scoreMap.style.setProperty("--score-map-cols", 1);
  elements.scoreMap.style.setProperty("--score-map-rows", 1);
  elements.scoreMapStage.style.setProperty("--score-map-rows", 1);
  elements.scoreMapStage.style.setProperty("--score-map-cols", 1);
  applyScoreMapDensity(1, 1);
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
    elements.scoreMapStage.style.setProperty("--score-map-rows", 1);
    elements.scoreMapStage.style.setProperty("--score-map-cols", 1);
    applyScoreMapDensity(1, 1);
    return;
  }

  const maxRow = Math.max(...positionedGrids.map((grid) => Number(grid.row_index)));
  const maxCol = Math.max(...positionedGrids.map((grid) => Number(grid.col_index)));
  const rowCount = maxRow + 1;
  const colCount = maxCol + 1;
  elements.scoreMap.style.setProperty("--score-map-rows", rowCount);
  elements.scoreMap.style.setProperty("--score-map-cols", colCount);
  elements.scoreMapStage.style.setProperty("--score-map-rows", rowCount);
  elements.scoreMapStage.style.setProperty("--score-map-cols", colCount);
  applyScoreMapDensity(rowCount, colCount);
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
  cancelDragSelection();
  state.gridsById = new Map(grids.map((grid) => [Number(grid.id), grid]));

  if (!grids.length) {
    renderEmptyGrids("GridCell がありません。");
    return;
  }

  renderScoreMap(grids);
  updateMapGridBoundaries(grids);
  pruneMissingSelectedGrids();
  if (state.selectedGridId && state.gridsById.has(state.selectedGridId)) {
    state.selectedGrid = state.gridsById.get(state.selectedGridId);
  } else {
    const [latestSelectedGrid] = selectedGrids();
    state.selectedGrid = latestSelectedGrid || null;
    state.selectedGridId = latestSelectedGrid ? latestSelectedGrid.id : null;
  }
  renderSelectedGrids();
  highlightSelectedScoreCells();
  highlightSelectedMapGridBoundaries();
}

async function loadAreas() {
  setMessage("メモグリッド一覧を取得しています。");
  elements.loadAreasButton.disabled = true;

  try {
    const data = await apiFetch("/api/maps/areas/");
    renderAreas(data.areas || []);
    updateMapPreview();
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

function clearSelectedAreaStateAfterDelete() {
  state.selectedAreaId = null;
  state.selectedAreaName = "";
  state.selectedGridId = null;
  state.selectedGrid = null;
  state.selectedGridIds.clear();
  state.gridsById = new Map();

  elements.selectedAreaLabel.textContent =
    "メモグリッドを選択すると、自動生成済みの GridCell を表示します。";
  elements.selectedShareAreaLabel.textContent = "先にメモグリッドを選択してください。";
  elements.reloadGridsButton.disabled = true;
  elements.loadSharesButton.disabled = true;
  elements.addShareButton.disabled = true;
  elements.sharesList.textContent = "共有相手はまだ読み込んでいません。";

  setShareMessage("");
  renderEmptyGrids("メモグリッドを選択してください。");
  clearMapAreaPreview();
}

async function deleteArea(areaId, areaName) {
  const confirmed = window.confirm(
    `メモグリッド「${areaName}」を削除します。関連するGridCell、採点、共有設定も削除されます。よろしいですか？`
  );

  if (!confirmed) {
    return;
  }

  const normalizedAreaId = Number(areaId);
  setMessage(`メモグリッド #${normalizedAreaId} を削除しています。`);

  try {
    await apiFetch(`/api/maps/areas/${normalizedAreaId}/`, {
      method: "DELETE",
    });

    if (normalizedAreaId === state.selectedAreaId) {
      clearSelectedAreaStateAfterDelete();
    }

    await loadAreas();
    setMessage(`メモグリッド #${normalizedAreaId} を削除しました。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function selectArea(areaId, areaName) {
  state.selectedAreaId = Number(areaId);
  state.selectedAreaName = areaName;
  clearSelectedGrids();
  elements.selectedAreaLabel.textContent = `選択中: #${areaId} ${areaName}`;
  elements.selectedShareAreaLabel.textContent = `選択中: #${areaId} ${areaName}`;
  elements.reloadGridsButton.disabled = false;
  elements.loadSharesButton.disabled = false;
  elements.addShareButton.disabled = false;
  elements.sharesList.textContent = "共有相手はまだ読み込んでいません。";
  setShareMessage("");
  clearMapGridBoundaries();

  document.querySelectorAll(".area-button").forEach((button) => {
    button.classList.toggle(
      "is-selected",
      Number(button.dataset.areaId) === state.selectedAreaId
    );
  });

  updateMapPreview();
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

function selectedGridIds() {
  return selectedGrids().map((grid) => grid.id);
}

function readMultiRatingMode() {
  const checkedInput = document.querySelector('input[name="multi-rating-mode"]:checked');
  return checkedInput ? checkedInput.value : "individual";
}

function updateRatingMode() {
  const mode = readMultiRatingMode();
  elements.individualRatingForm.hidden = mode !== "individual";
  elements.sameScoreRatingForm.hidden = mode !== "same";
}

function readIndividualScores() {
  return selectedGrids().map((grid) => {
    const scoreInput = document.querySelector(`[data-individual-score-for="${grid.id}"]`);
    return {
      grid,
      score: Number(scoreInput.value),
    };
  });
}

async function postRating(gridId, score, comment = "demo page rating") {
  return apiFetch(`/api/maps/grids/${gridId}/ratings/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      score,
      comment,
    }),
  });
}

async function submitRating(gridId, score, comment = "demo page rating") {
  setMessage(`GridCell #${gridId} を採点しています。`);
  await postRating(gridId, score, comment);
  await loadGrids();
  setMessage(`GridCell #${gridId} を採点しました。`, "success");
}

async function submitBulkRating(gridIds, score, comment = "demo page bulk rating") {
  await apiFetch("/api/maps/grids/bulk-ratings/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      grid_ids: gridIds,
      score,
      comment,
    }),
  });
  await loadGrids();
}

async function submitIndividualRatings(event) {
  event.preventDefault();

  const ratings = readIndividualScores();
  if (!ratings.length) {
    setSelectedGridMessage("採点する GridCell を選択してください。", "error");
    return;
  }

  const invalidRating = ratings.find((rating) => !isValidScore(rating.score));
  if (invalidRating) {
    setSelectedGridMessage(
      `GridCell #${invalidRating.grid.id} の score は 1 から 10 の整数で入力してください。`,
      "error"
    );
    return;
  }

  elements.individualRatingSubmit.disabled = true;
  elements.sameScoreRatingSubmit.disabled = true;
  setSelectedGridMessage(`${ratings.length} 件の GridCell を採点しています。`, "", true);

  try {
    for (const rating of ratings) {
      await postRating(rating.grid.id, rating.score, "demo page multi rating");
    }
    await loadGrids();
    clearSelectedGrids();
    setSelectedGridMessage(`${ratings.length} 件の GridCell を採点しました。`, "success");
  } catch (error) {
    renderSelectedGrids();
    setSelectedGridMessage(error.message, "error");
  }
}

async function submitSameScoreBulkRating(event) {
  event.preventDefault();

  const gridIds = selectedGridIds();
  if (!gridIds.length) {
    setSelectedGridMessage("採点する GridCell を選択してください。", "error");
    return;
  }

  const score = Number(elements.sameScoreInput.value);
  if (!isValidScore(score)) {
    setSelectedGridMessage("score は 1 から 10 の整数で入力してください。", "error");
    return;
  }

  elements.individualRatingSubmit.disabled = true;
  elements.sameScoreRatingSubmit.disabled = true;
  setSelectedGridMessage(
    `${gridIds.length} 件の GridCell を同じ値で採点しています。`,
    "",
    true
  );

  try {
    await submitBulkRating(gridIds, score);
    clearSelectedGrids();
    setSelectedGridMessage(
      `${gridIds.length} 件の GridCell を同じ値で採点しました。`,
      "success"
    );
  } catch (error) {
    renderSelectedGrids();
    setSelectedGridMessage(error.message, "error");
  }
}

elements.createAreaForm.addEventListener("submit", createArea);
elements.loadAreasButton.addEventListener("click", loadAreas);
elements.reloadGridsButton.addEventListener("click", loadGrids);
elements.loadSharesButton.addEventListener("click", loadShares);
elements.addShareForm.addEventListener("submit", addShare);
elements.individualRatingForm.addEventListener("submit", submitIndividualRatings);
elements.sameScoreRatingForm.addEventListener("submit", submitSameScoreBulkRating);
elements.clearSelectedGridsButton.addEventListener("click", clearSelectedGrids);
elements.ratingModeInputs.forEach((input) => {
  input.addEventListener("change", updateRatingMode);
});
elements.scoreMapViewModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    state.scoreMapViewMode = readScoreMapViewMode();
    cancelDragSelection();
    applyScoreMapViewMode();
  });
});
elements.areasList.addEventListener("click", (event) => {
  const deleteButton = event.target.closest("[data-delete-area-id]");
  if (deleteButton) {
    event.preventDefault();
    event.stopPropagation();
    deleteArea(
      deleteButton.dataset.deleteAreaId,
      deleteButton.dataset.deleteAreaName
    );
    return;
  }

  const button = event.target.closest("[data-area-id]");
  if (!button) {
    return;
  }

  selectArea(button.dataset.areaId, button.dataset.areaName);
});

elements.scoreMap.addEventListener("click", (event) => {
  if (state.suppressNextCellClick) {
    state.suppressNextCellClick = false;
    event.preventDefault();
    return;
  }

  const cell = event.target.closest("[data-grid-id]");
  if (!cell) {
    return;
  }

  toggleGridSelection(cell.dataset.gridId);
});

elements.scoreMapStage.addEventListener("pointerdown", startDragSelection);
elements.scoreMapStage.addEventListener("pointermove", updateDragSelection);
elements.scoreMapStage.addEventListener("pointerup", finishDragSelection);
elements.scoreMapStage.addEventListener("pointercancel", cancelDragSelection);

elements.scoreMap.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  const cell = event.target.closest("[data-grid-id]");
  if (!cell) {
    return;
  }

  event.preventDefault();
  toggleGridSelection(cell.dataset.gridId);
});

elements.selectedGridsList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-selected-grid]");
  if (!button) {
    return;
  }

  removeSelectedGrid(button.dataset.removeSelectedGrid);
});

elements.sharesList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete-share]");
  if (!button) {
    return;
  }

  deleteShare(button.dataset.deleteShare);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    cancelDragSelection();
    cancelLeafletDragSelection();
  }
});

applyScoreMapViewMode();
updateMapPreview();
updateRatingMode();
