(function () {
  const formElement = document.querySelector("#map-area-create-form");
  const statusElement = document.querySelector("#memo-grid-create-status");
  const submitButton = document.querySelector("#map-area-create-submit");
  const submitButtons = Array.from(document.querySelectorAll("[data-map-area-create-submit]"));
  const pageLoadingOverlay = document.querySelector("#site-loading-overlay");
  const mapPreviewElement = document.querySelector("#create-map-preview");
  const mapPreviewStatusElement = document.querySelector("#create-map-preview-status");
  const mapCenterCoordinateElement = document.querySelector("#create-map-center-coordinate");
  const applyMapCenterButton = document.querySelector("#apply-map-center-to-coordinates");
  const createMapZoomOutButton = document.querySelector("#create-map-zoom-out");
  const createMapZoomInButton = document.querySelector("#create-map-zoom-in");
  const createMapReturnButton = document.querySelector("#create-map-return-to-input-center");
  const createFormActionsElement = document.querySelector(".create-form-actions");
  const stickyActionElement = document.querySelector(".create-sticky-action");
  const autoScoreNoticeElement = document.querySelector("#auto-score-notice");
  const earthRadiusMeters = 6378137;
  const maxPreviewGridCells = 400;
  const mapPreviewState = {
    map: null,
    areaLayer: null,
    gridLayer: null,
  };

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
      const trimmedCookie = cookie.trim();
      if (trimmedCookie.startsWith(`${name}=`)) {
        return decodeURIComponent(trimmedCookie.slice(name.length + 1));
      }
    }
    return "";
  }

  function setStatus(message, type = "") {
    if (!statusElement) {
      return;
    }

    statusElement.textContent = message;
    statusElement.dataset.messageType = type;
    updateStickyCreateAction();
  }

  function showPageLoading() {
    if (!pageLoadingOverlay) {
      return;
    }
    pageLoadingOverlay.hidden = false;
    pageLoadingOverlay.setAttribute("aria-hidden", "false");
  }

  function hidePageLoading() {
    if (!pageLoadingOverlay) {
      return;
    }
    pageLoadingOverlay.hidden = true;
    pageLoadingOverlay.setAttribute("aria-hidden", "true");
  }

  function setSubmitButtonsDisabled(disabled) {
    if (submitButtons.length === 0 && submitButton) {
      submitButton.disabled = disabled;
      return;
    }
    submitButtons.forEach((button) => {
      button.disabled = disabled;
    });
  }

  function updateStickyCreateAction() {
    if (!createFormActionsElement || !stickyActionElement) {
      return;
    }

    const rect = createFormActionsElement.getBoundingClientRect();
    const bottomVisibilityMargin = 96;
    const isActionVisible = rect.top < window.innerHeight - bottomVisibilityMargin && rect.bottom > 0;
    document.body.classList.toggle("is-create-sticky-action-visible", !isActionVisible);
  }

  function updateAutoScoreNotice() {
    if (!autoScoreNoticeElement) {
      return;
    }

    autoScoreNoticeElement.hidden = fieldValue("region_feature_level") !== "auto";
    updateStickyCreateAction();
  }

  function setMapPreviewStatus(message, type = "") {
    if (!mapPreviewStatusElement) {
      return;
    }
    mapPreviewStatusElement.textContent = message;
    mapPreviewStatusElement.dataset.messageType = type;
  }

  function fieldValue(name) {
    const field = formElement.elements[name];
    if (!field) {
      return "";
    }
    return String(field.value).trim();
  }

  function numberValue(name) {
    const value = fieldValue(name);
    if (value === "") {
      return NaN;
    }
    return Number(value);
  }

  function integerValue(name) {
    const value = numberValue(name);
    if (!Number.isInteger(value)) {
      return NaN;
    }
    return value;
  }

  function formatCoordinate(value) {
    return Number(value).toFixed(6);
  }

  function updateMapCenterCoordinateDisplay() {
    if (!mapCenterCoordinateElement || !mapPreviewState.map) {
      return;
    }

    const center = mapPreviewState.map.getCenter();
    mapCenterCoordinateElement.textContent = (
      `地図中央: 緯度 ${formatCoordinate(center.lat)}\n/ 経度 ${formatCoordinate(center.lng)}`
    );
  }

  function applyMapCenterToCoordinateInputs() {
    if (!mapPreviewState.map) {
      return;
    }

    const center = mapPreviewState.map.getCenter();
    const centerLatInput = formElement.elements.center_lat;
    const centerLngInput = formElement.elements.center_lng;
    if (!centerLatInput || !centerLngInput) {
      return;
    }

    centerLatInput.value = formatCoordinate(center.lat);
    centerLngInput.value = formatCoordinate(center.lng);
    updateMapPreview();
  }

  function zoomCreateMapOut() {
    if (!mapPreviewState.map) {
      return;
    }

    mapPreviewState.map.zoomOut();
    updateMapCenterCoordinateDisplay();
  }

  function zoomCreateMapIn() {
    if (!mapPreviewState.map) {
      return;
    }

    mapPreviewState.map.zoomIn();
    updateMapCenterCoordinateDisplay();
  }

  function returnCreateMapToInputCenter() {
    if (!mapPreviewState.map) {
      return;
    }

    const centerLat = numberValue("center_lat");
    const centerLng = numberValue("center_lng");
    if (
      !Number.isFinite(centerLat) ||
      centerLat < -90 ||
      centerLat > 90 ||
      !Number.isFinite(centerLng) ||
      centerLng < -180 ||
      centerLng > 180
    ) {
      return;
    }

    mapPreviewState.map.setView([centerLat, centerLng], mapPreviewState.map.getZoom());
    updateMapCenterCoordinateDisplay();
    updateMapPreview();
  }

  function readPreviewInputs() {
    return {
      centerLat: numberValue("center_lat"),
      centerLng: numberValue("center_lng"),
      rows: integerValue("rows"),
      cols: integerValue("cols"),
      gridSizeMeters: numberValue("grid_size_meters"),
    };
  }

  function validatePreviewInputs(input) {
    if (!Number.isFinite(input.centerLat) || input.centerLat < -90 || input.centerLat > 90) {
      throw new Error("中心緯度は -90 から 90 の数値で入力してください。");
    }
    if (!Number.isFinite(input.centerLng) || input.centerLng < -180 || input.centerLng > 180) {
      throw new Error("中心経度は -180 から 180 の数値で入力してください。");
    }
    if (!Number.isInteger(input.rows) || input.rows < 1) {
      throw new Error("縦方向のマス数は 1 以上の整数で入力してください。");
    }
    if (!Number.isInteger(input.cols) || input.cols < 1) {
      throw new Error("横方向のマス数は 1 以上の整数で入力してください。");
    }
    if (!Number.isFinite(input.gridSizeMeters) || input.gridSizeMeters < 1) {
      throw new Error("1マスの大きさは 1 以上の数値で入力してください。");
    }
  }

  function calculatePreviewBounds(input) {
    const totalHeightMeters = input.rows * input.gridSizeMeters;
    const totalWidthMeters = input.cols * input.gridSizeMeters;
    const centerLatRadians = input.centerLat * Math.PI / 180;
    const latitudeDelta = totalHeightMeters / earthRadiusMeters * 180 / Math.PI / 2;
    const longitudeScale = Math.max(Math.cos(centerLatRadians), 0.000001);
    const longitudeDelta = totalWidthMeters / (earthRadiusMeters * longitudeScale) * 180 / Math.PI / 2;

    return {
      north: input.centerLat + latitudeDelta,
      south: input.centerLat - latitudeDelta,
      east: input.centerLng + longitudeDelta,
      west: input.centerLng - longitudeDelta,
    };
  }

  function boundsArray(bounds) {
    return [
      [bounds.south, bounds.west],
      [bounds.north, bounds.east],
    ];
  }

  function ensureMapPreview() {
    if (!mapPreviewElement || !window.L) {
      return null;
    }

    if (mapPreviewState.map) {
      return mapPreviewState.map;
    }

    mapPreviewState.map = window.L.map(mapPreviewElement, {
      scrollWheelZoom: false,
    }).setView([35.681236, 139.767125], 13);

    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(mapPreviewState.map);

    mapPreviewState.gridLayer = window.L.layerGroup().addTo(mapPreviewState.map);
    mapPreviewState.map.on("moveend zoomend", updateMapCenterCoordinateDisplay);
    updateMapCenterCoordinateDisplay();
    window.setTimeout(() => {
      mapPreviewState.map.invalidateSize();
      updateMapCenterCoordinateDisplay();
    }, 0);

    return mapPreviewState.map;
  }

  function clearMapPreviewLayers() {
    if (mapPreviewState.areaLayer) {
      mapPreviewState.areaLayer.remove();
      mapPreviewState.areaLayer = null;
    }
    if (mapPreviewState.gridLayer) {
      mapPreviewState.gridLayer.clearLayers();
    }
  }

  function renderPreviewGridCells(input, bounds) {
    if (!mapPreviewState.gridLayer || input.rows * input.cols > maxPreviewGridCells) {
      return false;
    }

    const latStep = (bounds.north - bounds.south) / input.rows;
    const lngStep = (bounds.east - bounds.west) / input.cols;

    for (let row = 0; row < input.rows; row += 1) {
      const north = bounds.north - latStep * row;
      const south = north - latStep;
      for (let col = 0; col < input.cols; col += 1) {
        const west = bounds.west + lngStep * col;
        const east = west + lngStep;
        window.L.rectangle([[south, west], [north, east]], {
          color: "#6f8faf",
          weight: 1,
          opacity: 0.45,
          fillOpacity: 0,
          interactive: false,
          className: "create-map-preview-grid-cell",
        }).addTo(mapPreviewState.gridLayer);
      }
    }

    return true;
  }

  function updateMapPreview() {
    const map = ensureMapPreview();
    if (!map) {
      setMapPreviewStatus("地図ライブラリを読み込めませんでした。", "error");
      return;
    }

    clearMapPreviewLayers();

    const input = readPreviewInputs();
    try {
      validatePreviewInputs(input);
    } catch (error) {
      setMapPreviewStatus(error.message);
      return;
    }

    const bounds = calculatePreviewBounds(input);
    mapPreviewState.areaLayer = window.L.rectangle(boundsArray(bounds), {
      color: "#176f5c",
      weight: 3,
      opacity: 0.9,
      fillColor: "#d8f3e5",
      fillOpacity: 0.18,
      interactive: false,
      className: "create-map-preview-area",
    }).addTo(map);

    const renderedGrid = renderPreviewGridCells(input, bounds);
    map.fitBounds(boundsArray(bounds), { padding: [24, 24], maxZoom: 18 });
    updateMapCenterCoordinateDisplay();
    setMapPreviewStatus(
      renderedGrid
        ? "入力値から作成予定範囲とマス境界を概算表示しています。"
        : `入力値から作成予定範囲を概算表示しています。マス数が多いため境界表示は省略しています。`,
      "success"
    );
  }

  function readInitialScoreSettings() {
    const selectedValue = fieldValue("region_feature_level");
    let initialScoreMode = "manual";
    let regionFeatureLevel = Number(selectedValue);

    if (selectedValue === "auto") {
      initialScoreMode = "auto";
      regionFeatureLevel = 0;
    }

    const initialScoreModeInput = formElement.elements.initial_score_mode;
    if (initialScoreModeInput) {
      initialScoreModeInput.value = initialScoreMode;
    }

    return {
      initial_score_mode: initialScoreMode,
      region_feature_level: regionFeatureLevel,
    };
  }

  function buildPayload() {
    const name = fieldValue("name");
    const centerLat = numberValue("center_lat");
    const centerLng = numberValue("center_lng");
    const rows = integerValue("rows");
    const cols = integerValue("cols");
    const gridSizeMeters = numberValue("grid_size_meters");
    const initialScoreSettings = readInitialScoreSettings();

    if (!name) {
      throw new Error("名前を入力してください。");
    }
    if (!Number.isFinite(centerLat)) {
      throw new Error("中心緯度は数値で入力してください。");
    }
    if (!Number.isFinite(centerLng)) {
      throw new Error("中心経度は数値で入力してください。");
    }
    if (!Number.isFinite(gridSizeMeters) || gridSizeMeters < 1) {
      throw new Error("1マスの大きさは 1 以上の数値で入力してください。");
    }
    if (!Number.isInteger(rows) || rows < 1) {
      throw new Error("縦方向のマス数は 1 以上の整数で入力してください。");
    }
    if (!Number.isInteger(cols) || cols < 1) {
      throw new Error("横方向のマス数は 1 以上の整数で入力してください。");
    }
    if (
      initialScoreSettings.initial_score_mode === "manual" &&
      (!Number.isInteger(initialScoreSettings.region_feature_level) ||
        initialScoreSettings.region_feature_level < 0 ||
        initialScoreSettings.region_feature_level > 3)
    ) {
      throw new Error("初期スコア設定を選択してください。");
    }

    return {
      name,
      description: fieldValue("description"),
      center_lat: centerLat,
      center_lng: centerLng,
      grid_size_meters: gridSizeMeters,
      region_feature_level: initialScoreSettings.region_feature_level,
      initial_score_mode: initialScoreSettings.initial_score_mode,
      rows,
      cols,
    };
  }

  async function readResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return null;
    }
    return response.json();
  }

  function formatErrorData(data) {
    if (!data) {
      return "";
    }
    if (data.detail) {
      return String(data.detail);
    }
    if (Array.isArray(data)) {
      return data.join(" ");
    }
    if (typeof data === "object") {
      const fieldLabels = {
        name: "名前",
        description: "説明",
        center_lat: "中心緯度",
        center_lng: "中心経度",
        grid_size_meters: "1マスの大きさ",
        rows: "縦方向のマス数",
        cols: "横方向のマス数",
        initial_score_mode: "初期スコア設定",
        region_feature_level: "初期スコア設定",
        non_field_errors: "入力内容",
      };
      return Object.entries(data)
        .map(([key, value]) => {
          const detail = Array.isArray(value) ? value.join(" ") : String(value);
          return `${fieldLabels[key] || key}: ${detail}`;
        })
        .join(" / ");
    }
    return String(data);
  }

  async function submitMapArea() {
    let payload;
    try {
      payload = buildPayload();
    } catch (error) {
      setStatus(error.message, "error");
      return;
    }

    setSubmitButtonsDisabled(true);
    setStatus("メモグリッドを作成しています。");
    showPageLoading();

    try {
      const response = await fetch("/api/maps/areas/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
      });
      const data = await readResponse(response);

      if (!response.ok) {
        const detail = formatErrorData(data);
        throw new Error(
          detail
            ? `通信エラー ${response.status}. ${detail}`
            : `通信エラー ${response.status}.`
        );
      }

      if (!data || !data.id) {
        throw new Error("作成されたメモグリッドIDを取得できませんでした。");
      }

      setStatus("メモグリッドを作成しました。詳細画面へ移動します。", "success");
      window.location.href = `/maps/${data.id}/`;
    } catch (error) {
      setStatus(`メモグリッドを作成できませんでした。${error.message}`, "error");
      setSubmitButtonsDisabled(false);
    } finally {
      hidePageLoading();
    }
  }

  if (formElement) {
    updateMapPreview();
    updateAutoScoreNotice();
    updateStickyCreateAction();

    ["center_lat", "center_lng", "rows", "cols", "grid_size_meters"].forEach((name) => {
      const field = formElement.elements[name];
      if (!field) {
        return;
      }
      field.addEventListener("input", updateMapPreview);
      field.addEventListener("change", updateMapPreview);
    });

    const initialScoreSelect = formElement.elements.region_feature_level;
    if (initialScoreSelect) {
      initialScoreSelect.addEventListener("change", updateAutoScoreNotice);
    }

    if (applyMapCenterButton) {
      applyMapCenterButton.addEventListener("click", applyMapCenterToCoordinateInputs);
    }

    if (createMapZoomOutButton) {
      createMapZoomOutButton.addEventListener("click", zoomCreateMapOut);
    }

    if (createMapZoomInButton) {
      createMapZoomInButton.addEventListener("click", zoomCreateMapIn);
    }

    if (createMapReturnButton) {
      createMapReturnButton.addEventListener("click", returnCreateMapToInputCenter);
    }

    window.addEventListener("resize", () => {
      if (!mapPreviewState.map) {
        updateStickyCreateAction();
        return;
      }
      mapPreviewState.map.invalidateSize();
      updateMapCenterCoordinateDisplay();
      updateStickyCreateAction();
    });

    window.addEventListener("scroll", updateStickyCreateAction, { passive: true });

    formElement.addEventListener("submit", (event) => {
      event.preventDefault();
      submitMapArea();
    });
  }
})();
