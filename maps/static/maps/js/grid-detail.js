(function () {
  const rootElement = document.querySelector("#grid-detail-root");
  const messageElement = document.querySelector("#grid-cell-list-message");
  const countElement = document.querySelector("#grid-cell-count");
  const listElement = document.querySelector("#grid-cell-list");
  const selectedGridDetailElement = document.querySelector(
    "#selected-grid-cell-detail"
  );
  const selectedGridCountElement = document.querySelector("#selected-grid-cell-count");
  const clearSelectedGridsButton = document.querySelector("#clear-selected-grids");
  const ratingFormContainer = document.querySelector("#grid-rating-form-container");
  const bulkRatingFormContainer = document.querySelector("#bulk-rating-form-container");
  const deleteAreaButton = document.querySelector("#delete-current-area");
  const deleteStatusElement = document.querySelector("#area-delete-status");
  const shareMessageElement = document.querySelector("#share-management-message");
  const shareAddForm = document.querySelector("#share-add-form");
  const shareUsernameInput = document.querySelector("#share-username");
  const shareAddSubmitButton = document.querySelector("#share-add-submit");
  const shareListElement = document.querySelector("#share-list");
  const mapPreviewElement = document.querySelector("#map-preview");
  const mapPreviewStatusElement = document.querySelector("#map-preview-status");
  const maxVisibleGridCount = 50;
  const utils = window.GridDetailUtils;
  if (!utils) {
    console.error("GridDetailUtils is not loaded.");
    return;
  }
  const api = window.GridDetailApi;
  if (!api) {
    console.error("GridDetailApi is not loaded.");
    return;
  }
  const {
    textOrFallback,
    formatNumber,
    formatCoordinate,
    formatDateTime,
    displayIndex,
    autoScoreLabel,
    hasAutoScoreBreakdown,
    formatAutoScoreValue,
    autoScoreReasonLabels,
    formatScoreLabel,
  } = utils;
  const state = {
    gridsById: new Map(),
    selectedGridId: null,
    // selectedGridIds が正式な選択集合。selectedGridId は詳細・単体採点の主対象。
    selectedGridIds: new Set(),
    leafletMap: null,
    mapAreaRectangle: null,
    gridBoundaryLayer: null,
    scoreLabelLayer: null,
    mapGridRectanglesById: new Map(),
    selectionDrag: {
      isDragging: false,
      startLatLng: null,
      rectangle: null,
      wasMapDraggingEnabled: true,
      suppressNextClick: false,
    },
  };

  function setMessage(text, type = "") {
    if (!messageElement) {
      return;
    }
    messageElement.textContent = text;
    messageElement.dataset.messageType = type;
  }

  function setDeleteStatus(text, type = "") {
    if (!deleteStatusElement) {
      return;
    }
    deleteStatusElement.textContent = text;
    deleteStatusElement.dataset.messageType = type;
  }

  function setShareMessage(text, type = "") {
    if (!shareMessageElement) {
      return;
    }
    shareMessageElement.textContent = text;
    shareMessageElement.dataset.messageType = type;
  }

  function setShareListMessage(text) {
    if (!shareListElement) {
      return;
    }
    shareListElement.textContent = text;
  }

  function setCount(text) {
    if (!countElement) {
      return;
    }
    countElement.textContent = text;
  }

  function setSelectedGridCount(count) {
    if (!selectedGridCountElement) {
      return;
    }
    selectedGridCountElement.textContent = `選択中: ${count}件`;
  }

  function updateClearSelectedButton() {
    if (!clearSelectedGridsButton) {
      return;
    }
    clearSelectedGridsButton.hidden = state.selectedGridIds.size === 0;
  }

  function clearList() {
    if (!listElement) {
      return;
    }
    listElement.replaceChildren();
  }

  function createGridItem(grid) {
    const item = document.createElement("li");
    const gridId = Number(grid.id);
    item.className = "grid-cell-item";
    item.dataset.gridId = textOrFallback(grid.id, "");
    item.classList.toggle("is-selected", state.selectedGridIds.has(gridId));

    const summary = document.createElement("span");
    summary.className = "grid-cell-summary";
    summary.textContent = [
      `#${textOrFallback(grid.id)}`,
      `行 ${displayIndex(grid.row_index)}`,
      `列 ${displayIndex(grid.col_index)}`,
      `初期スコア ${formatNumber(grid.initial_score)}`,
      `ユーザー平均スコア ${formatNumber(grid.average_user_score)}`,
      `採点数 ${formatNumber(grid.rating_count)}`,
      `表示スコア ${formatNumber(grid.calculated_score)}`,
    ].join(" / ");

    const selectButton = document.createElement("button");
    selectButton.type = "button";
    selectButton.className = "secondary-button";
    selectButton.dataset.selectGridId = textOrFallback(grid.id, "");
    selectButton.textContent = state.selectedGridIds.has(gridId) ? "選択中" : "選択";

    item.append(summary, " ", selectButton);
    return item;
  }

  function setSelectedGridDetail(text) {
    if (!selectedGridDetailElement) {
      return;
    }
    selectedGridDetailElement.textContent = text;
  }

  function setRatingFormMessage(text) {
    if (!ratingFormContainer) {
      return;
    }
    ratingFormContainer.textContent = text;
  }

  function setBulkRatingFormMessage(text) {
    if (!bulkRatingFormContainer) {
      return;
    }
    bulkRatingFormContainer.textContent = text;
  }

  function createDetailItem(label, value) {
    const item = document.createElement("li");
    item.textContent = `${label}: ${value}`;
    return item;
  }

  function createAutoScoreRow(key, value) {
    const row = document.createElement("div");
    row.className = "auto-score-breakdown-row";

    const term = document.createElement("dt");
    term.textContent = autoScoreLabel(key);

    const description = document.createElement("dd");
    description.textContent = formatAutoScoreValue(value);

    row.append(term, description);
    return row;
  }

  function createAutoScoreBreakdownSection(grid) {
    const section = document.createElement("section");
    section.className = "auto-score-breakdown-section";

    const heading = document.createElement("h4");
    heading.textContent = "自動採点理由";
    section.appendChild(heading);

    const breakdown = grid ? grid.auto_score_breakdown : null;
    if (!hasAutoScoreBreakdown(breakdown)) {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "auto-score-breakdown-empty";
      emptyMessage.textContent = "このマスには自動採点理由の情報がありません。";
      section.appendChild(emptyMessage);
      return section;
    }

    const scoreKeys = [
      "clamped_score",
      "base_score",
      "diversity_bonus",
      "context_bonus",
      "penalty",
      "raw_score",
    ];
    const scoreList = document.createElement("dl");
    scoreList.className = "auto-score-breakdown-list";
    scoreKeys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(breakdown, key)) {
        scoreList.appendChild(createAutoScoreRow(key, breakdown[key]));
      }
    });
    if (scoreList.children.length > 0) {
      section.appendChild(scoreList);
    }

    const reasonLabels = autoScoreReasonLabels(breakdown);
    const reasonBlock = document.createElement("div");
    reasonBlock.className = "auto-score-reason-block";
    const reasonHeading = document.createElement("p");
    reasonHeading.textContent = "主な理由";
    reasonBlock.appendChild(reasonHeading);

    if (reasonLabels.length > 0) {
      const reasonList = document.createElement("ul");
      reasonList.className = "auto-score-reasons";
      reasonLabels.forEach((label) => {
        const item = document.createElement("li");
        item.textContent = label;
        reasonList.appendChild(item);
      });
      reasonBlock.appendChild(reasonList);
    } else {
      const emptyReason = document.createElement("p");
      emptyReason.className = "auto-score-breakdown-empty";
      emptyReason.textContent = "主な理由は記録されていません。";
      reasonBlock.appendChild(emptyReason);
    }
    section.appendChild(reasonBlock);

    const details = document.createElement("details");
    details.className = "auto-score-breakdown-details";
    const summary = document.createElement("summary");
    summary.textContent = "詳細項目";
    const detailList = document.createElement("dl");
    detailList.className = "auto-score-breakdown-list";

    Object.entries(breakdown).forEach(([key, value]) => {
      if (scoreKeys.includes(key)) {
        return;
      }
      detailList.appendChild(createAutoScoreRow(key, value));
    });

    if (detailList.children.length > 0) {
      details.append(summary, detailList);
      section.appendChild(details);
    }

    return section;
  }

  function renderSelectedGridDetail(grid) {
    if (!selectedGridDetailElement) {
      return;
    }

    selectedGridDetailElement.replaceChildren();

    if (!grid) {
      selectedGridDetailElement.textContent = "マスを選択してください。";
      return;
    }

    const heading = document.createElement("h3");
    heading.textContent = `マス #${textOrFallback(grid.id)}`;

    const position = document.createElement("p");
    position.textContent = `行 ${displayIndex(grid.row_index)} / 列 ${displayIndex(
      grid.col_index
    )}`;

    const detailList = document.createElement("ul");
    detailList.className = "selected-grid-cell-detail-list";
    detailList.append(
      createDetailItem("初期スコア", formatNumber(grid.initial_score)),
      createDetailItem("ユーザー平均スコア", formatNumber(grid.average_user_score)),
      createDetailItem("採点数", formatNumber(grid.rating_count)),
      createDetailItem("表示スコア", formatNumber(grid.calculated_score)),
      createDetailItem(
        "範囲",
        [
          `north ${formatCoordinate(grid.north)}`,
          `south ${formatCoordinate(grid.south)}`,
          `east ${formatCoordinate(grid.east)}`,
          `west ${formatCoordinate(grid.west)}`,
        ].join(" / ")
      ),
      createDetailItem("スコア更新日時", formatDateTime(grid.score_updated_at))
    );

    selectedGridDetailElement.append(
      heading,
      position,
      detailList,
      createAutoScoreBreakdownSection(grid)
    );
  }

  function selectedGrids() {
    return Array.from(state.selectedGridIds)
      .map((gridId) => state.gridsById.get(gridId))
      .filter(Boolean);
  }

  function renderSelectedGridSelection() {
    if (!selectedGridDetailElement) {
      return;
    }

    const grids = selectedGrids();
    setSelectedGridCount(grids.length);
    updateClearSelectedButton();

    if (grids.length === 0) {
      renderSelectedGridDetail(null);
      return;
    }

    if (grids.length === 1) {
      renderSelectedGridDetail(grids[0]);
      return;
    }

    selectedGridDetailElement.replaceChildren();

    const list = document.createElement("ul");
    list.className = "selected-grid-cell-summary-list";
    grids.forEach((grid) => {
      const item = document.createElement("li");
      item.className = "selected-grid-cell-summary-item";

      const summary = document.createElement("span");
      summary.textContent = `マス #${textOrFallback(grid.id)}: ${[
        `行 ${displayIndex(grid.row_index)}`,
        `列 ${displayIndex(grid.col_index)}`,
        `表示スコア ${formatNumber(grid.calculated_score)}`,
      ].join(" / ")}`;

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "secondary-button selected-grid-cell-remove-button";
      removeButton.dataset.removeSelectedGridId = textOrFallback(grid.id, "");
      removeButton.textContent = "解除";

      item.append(summary, removeButton);
      list.appendChild(item);
    });

    selectedGridDetailElement.appendChild(list);
  }

  function removeGridSelection(gridId) {
    const numericGridId = Number(gridId);
    if (!state.selectedGridIds.has(numericGridId)) {
      return;
    }

    state.selectedGridIds.delete(numericGridId);

    if (state.selectedGridIds.size === 0) {
      state.selectedGridId = null;
    } else if (
      !state.selectedGridId ||
      !state.selectedGridIds.has(Number(state.selectedGridId))
    ) {
      state.selectedGridId = Array.from(state.selectedGridIds)[
        state.selectedGridIds.size - 1
      ];
    }

    renderSelectionState();
  }

  function setRatingFormStatus(text, type = "") {
    if (!ratingFormContainer) {
      return;
    }

    const statusElement = ratingFormContainer.querySelector(
      "[data-rating-form-status]"
    );
    if (!statusElement) {
      return;
    }

    statusElement.textContent = text;
    statusElement.dataset.messageType = type;
  }

  function setBulkRatingFormStatus(text, type = "") {
    if (!bulkRatingFormContainer) {
      return;
    }

    const statusElement = bulkRatingFormContainer.querySelector(
      "[data-bulk-rating-form-status]"
    );
    if (!statusElement) {
      return;
    }

    statusElement.textContent = text;
    statusElement.dataset.messageType = type;
  }

  function renderRatingForm(grid, message = "", messageType = "") {
    if (!ratingFormContainer) {
      return;
    }

    ratingFormContainer.replaceChildren();

    if (!grid) {
      ratingFormContainer.textContent =
        "マスを選択すると、採点フォームを表示します。";
      return;
    }

    const target = document.createElement("p");
    target.className = "rating-form-target";
    target.textContent = `対象: マス #${textOrFallback(grid.id)}`;

    const form = document.createElement("form");
    form.className = "rating-form";
    form.dataset.ratingGridId = textOrFallback(grid.id, "");

    const scoreLabel = document.createElement("label");
    scoreLabel.textContent = "score";
    const scoreInput = document.createElement("input");
    scoreInput.type = "number";
    scoreInput.name = "score";
    scoreInput.min = "1";
    scoreInput.max = "10";
    scoreInput.step = "1";
    scoreInput.value = "5";
    scoreLabel.append(" ", scoreInput);

    const commentLabel = document.createElement("label");
    commentLabel.textContent = "comment";
    const commentInput = document.createElement("textarea");
    commentInput.name = "comment";
    commentInput.rows = 3;
    commentInput.placeholder = "任意入力";
    commentLabel.append(" ", commentInput);

    const submitButton = document.createElement("button");
    submitButton.type = "submit";
    submitButton.textContent = "採点する";

    const status = document.createElement("p");
    status.className = "rating-form-status";
    status.dataset.ratingFormStatus = "";
    status.dataset.messageType = messageType;
    status.textContent = message;

    form.append(scoreLabel, commentLabel, submitButton, status);
    ratingFormContainer.append(target, form);
  }

  function renderRatingFormForSelection(message = "", messageType = "") {
    const grids = selectedGrids();

    if (grids.length === 0) {
      renderRatingForm(null);
      return;
    }

    if (grids.length === 1) {
      renderRatingForm(grids[0], message, messageType);
      return;
    }

    setRatingFormMessage(
      "複数のマスを選択中です。単体採点フォームは1件選択時のみ使用できます。"
    );
  }

  function renderBulkRatingFormForSelection(message = "", messageType = "") {
    if (!bulkRatingFormContainer) {
      return;
    }

    const selectedCount = state.selectedGridIds.size;
    bulkRatingFormContainer.replaceChildren();

    if (selectedCount < 2) {
      bulkRatingFormContainer.textContent =
        "複数のマスを選択すると、一括採点フォームを表示します。";
      return;
    }

    const target = document.createElement("p");
    target.className = "rating-form-target";
    target.textContent = `対象: ${selectedCount}件のマス`;

    const form = document.createElement("form");
    form.className = "rating-form bulk-rating-form";
    form.dataset.bulkRatingForm = "";

    const scoreLabel = document.createElement("label");
    scoreLabel.textContent = "score";
    const scoreInput = document.createElement("input");
    scoreInput.type = "number";
    scoreInput.name = "score";
    scoreInput.min = "1";
    scoreInput.max = "10";
    scoreInput.step = "1";
    scoreInput.value = "5";
    scoreLabel.append(" ", scoreInput);

    const commentLabel = document.createElement("label");
    commentLabel.textContent = "comment";
    const commentInput = document.createElement("textarea");
    commentInput.name = "comment";
    commentInput.rows = 3;
    commentInput.placeholder = "任意メモ";
    commentLabel.append(" ", commentInput);

    const submitButton = document.createElement("button");
    submitButton.type = "submit";
    submitButton.textContent = "一括採点する";

    const status = document.createElement("p");
    status.className = "rating-form-status";
    status.dataset.bulkRatingFormStatus = "";
    status.dataset.messageType = messageType;
    status.textContent = message;

    form.append(scoreLabel, commentLabel, submitButton, status);
    bulkRatingFormContainer.append(target, form);
  }

  function updateSelectedGridListState() {
    if (!listElement) {
      return;
    }

    listElement.querySelectorAll(".grid-cell-item").forEach((item) => {
      const itemGridId = Number(item.dataset.gridId);
      const isSelected = state.selectedGridIds.has(itemGridId);
      item.classList.toggle("is-selected", isSelected);

      const selectButton = item.querySelector("[data-select-grid-id]");
      if (selectButton) {
        selectButton.textContent = isSelected ? "選択中" : "選択";
      }
    });
  }

  function gridScoreStyle(grid) {
    const rawScore = grid ? grid.calculated_score : undefined;

    if (rawScore === null || rawScore === undefined || rawScore === "") {
      return {
        color: "#8a94a1",
        fillColor: "#e5e7eb",
        fillOpacity: 0.08,
      };
    }

    const score = Number(rawScore);

    if (!Number.isFinite(score)) {
      return {
        color: "#8a94a1",
        fillColor: "#e5e7eb",
        fillOpacity: 0.08,
      };
    }

    if (score < 3) {
      return {
        color: "#b84a4a",
        fillColor: "#f8dede",
        fillOpacity: 0.08,
      };
    }
    if (score < 6) {
      return {
        color: "#d08a2f",
        fillColor: "#fdebd0",
        fillOpacity: 0.08,
      };
    }
    if (score < 8) {
      return {
        color: "#8da63a",
        fillColor: "#edf7d4",
        fillOpacity: 0.08,
      };
    }

    return {
      color: "#176f5c",
      fillColor: "#d8f3e5",
      fillOpacity: 0.08,
    };
  }

  function mapGridRectangleStyle(grid, isSelected) {
    const scoreStyle = gridScoreStyle(grid);

    return {
      color: scoreStyle.color,
      weight: isSelected ? 3 : 1,
      opacity: isSelected ? 0.95 : 0.65,
      fill: true,
      fillColor: scoreStyle.fillColor,
      fillOpacity: isSelected
        ? Math.min(scoreStyle.fillOpacity + 0.1, 0.24)
        : scoreStyle.fillOpacity,
    };
  }

  function applyGridRectangleStyle(grid, rectangle, isSelected) {
    rectangle.setStyle(mapGridRectangleStyle(grid, isSelected));
  }

  function updateSelectedMapGridState() {
    state.mapGridRectanglesById.forEach((rectangle, gridId) => {
      const grid = state.gridsById.get(gridId);
      if (!grid) {
        return;
      }

      const isSelected = state.selectedGridIds.has(gridId);
      applyGridRectangleStyle(grid, rectangle, isSelected);
      if (isSelected) {
        rectangle.bringToFront();
      }
    });

    if (state.mapAreaRectangle) {
      state.mapAreaRectangle.bringToFront();
    }
  }

  function renderSelectionState(
    message = "",
    messageType = "",
    bulkMessage = "",
    bulkMessageType = ""
  ) {
    renderSelectedGridSelection();
    renderRatingFormForSelection(message, messageType);
    renderBulkRatingFormForSelection(bulkMessage, bulkMessageType);
    updateSelectedGridListState();
    updateSelectedMapGridState();
  }

  function selectSingleGrid(gridId) {
    const numericGridId = Number(gridId);
    if (!state.gridsById.has(numericGridId)) {
      return;
    }

    state.selectedGridId = numericGridId;
    state.selectedGridIds = new Set([numericGridId]);
    renderSelectionState();
  }

  function toggleGridSelection(gridId) {
    const numericGridId = Number(gridId);
    if (!state.gridsById.has(numericGridId)) {
      return;
    }

    const wasSelected = state.selectedGridIds.has(numericGridId);
    if (wasSelected) {
      state.selectedGridIds.delete(numericGridId);
    } else {
      state.selectedGridIds.add(numericGridId);
    }

    state.selectedGridId = wasSelected
      ? Array.from(state.selectedGridIds)[state.selectedGridIds.size - 1] || null
      : numericGridId;
    if (state.selectedGridIds.size === 1) {
      state.selectedGridId = Array.from(state.selectedGridIds)[0];
    }
    renderSelectionState();
  }

  function clearSelectedGrids() {
    state.selectedGridId = null;
    state.selectedGridIds = new Set();
    renderSelectionState();
  }

  function selectGrid(gridId) {
    selectSingleGrid(gridId);
  }

  function renderGrids(grids, options = {}) {
    const previousSelectedGridIds = new Set(state.selectedGridIds);
    const previousSelectedGridId = state.selectedGridId;
    clearList();
    state.gridsById = new Map();
    state.selectedGridId = null;
    state.selectedGridIds = new Set();

    if (!Array.isArray(grids) || grids.length === 0) {
      setCount("");
      setMessage("このメモグリッドには、まだマスがありません。");
      setSelectedGridDetail("表示できるマスがありません。");
      setRatingFormMessage("表示できるマスがないため、採点フォームは表示できません。");
      setBulkRatingFormMessage(
        "表示できるマスがないため、一括採点フォームは表示できません。"
      );
      setSelectedGridCount(0);
      updateClearSelectedButton();
      clearMapGridBoundaries();
      return;
    }

    state.gridsById = new Map(
      grids.map((grid) => [Number(grid.id), grid])
    );
    setCount(`マス数: ${grids.length}`);
    setMessage("マス一覧を取得しました。");

    const requestedSelectedGridIds = options.selectedGridIds
      ? new Set(Array.from(options.selectedGridIds).map(Number))
      : options.selectedGridId
        ? new Set([Number(options.selectedGridId)])
        : previousSelectedGridIds;
    state.selectedGridIds = new Set(
      Array.from(requestedSelectedGridIds).filter((gridId) =>
        state.gridsById.has(gridId)
      )
    );
    if (options.selectedGridId && state.selectedGridIds.has(Number(options.selectedGridId))) {
      state.selectedGridId = Number(options.selectedGridId);
    } else if (state.selectedGridIds.size === 1) {
      state.selectedGridId = Array.from(state.selectedGridIds)[0];
    } else if (state.selectedGridIds.size > 1) {
      const remainingPreviousTarget = Number(previousSelectedGridId);
      state.selectedGridId = state.selectedGridIds.has(remainingPreviousTarget)
        ? remainingPreviousTarget
        : Array.from(state.selectedGridIds)[state.selectedGridIds.size - 1];
    }

    const visibleGrids = grids.slice(0, maxVisibleGridCount);
    const list = document.createElement("ul");
    list.className = "grid-cell-list-items";
    visibleGrids.forEach((grid) => {
      list.appendChild(createGridItem(grid));
    });
    listElement.appendChild(list);

    if (grids.length > maxVisibleGridCount) {
      const limitNote = document.createElement("p");
      limitNote.textContent = `先頭${maxVisibleGridCount}件を表示しています。`;
      listElement.appendChild(limitNote);
    }

    renderMapGridBoundaries(grids);
    renderSelectionState(
      options.ratingMessage || "",
      options.ratingMessageType || "",
      options.bulkRatingMessage || "",
      options.bulkRatingMessageType || ""
    );
  }

  function areaId() {
    return rootElement ? rootElement.dataset.areaId : "";
  }

  function setMapPreviewStatus(text, type = "") {
    if (!mapPreviewStatusElement) {
      return;
    }
    mapPreviewStatusElement.textContent = text;
    mapPreviewStatusElement.dataset.messageType = type;
  }

  function leafletAvailable() {
    return typeof window.L !== "undefined";
  }

  function readMapAreaBounds() {
    if (!rootElement) {
      return null;
    }

    const north = Number(rootElement.dataset.areaNorth);
    const south = Number(rootElement.dataset.areaSouth);
    const east = Number(rootElement.dataset.areaEast);
    const west = Number(rootElement.dataset.areaWest);

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
    const north = Number(grid.north);
    const south = Number(grid.south);
    const east = Number(grid.east);
    const west = Number(grid.west);

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

  function gridCellCenter(grid) {
    const north = Number(grid.north);
    const south = Number(grid.south);
    const east = Number(grid.east);
    const west = Number(grid.west);

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
      (north + south) / 2,
      (east + west) / 2,
    ];
  }

  function selectionDragStyle() {
    return {
      color: "#2563eb",
      weight: 2,
      dashArray: "4 4",
      fill: true,
      fillColor: "#2563eb",
      fillOpacity: 0.08,
      interactive: false,
    };
  }

  function boundsFromLatLngs(startLatLng, endLatLng) {
    if (!leafletAvailable() || !startLatLng || !endLatLng) {
      return null;
    }
    return window.L.latLngBounds(startLatLng, endLatLng);
  }

  function gridLeafletBounds(grid) {
    if (!leafletAvailable()) {
      return null;
    }

    const bounds = gridCellBounds(grid);
    return bounds ? window.L.latLngBounds(bounds) : null;
  }

  function cleanupDragSelection() {
    if (state.selectionDrag.rectangle) {
      state.selectionDrag.rectangle.remove();
    }

    if (
      state.leafletMap &&
      state.leafletMap.dragging &&
      state.selectionDrag.wasMapDraggingEnabled
    ) {
      state.leafletMap.dragging.enable();
    }

    state.selectionDrag.isDragging = false;
    state.selectionDrag.startLatLng = null;
    state.selectionDrag.rectangle = null;
    state.selectionDrag.wasMapDraggingEnabled = true;
  }

  function startDragSelection(latlng) {
    if (!state.leafletMap || !leafletAvailable() || !latlng) {
      return;
    }

    cleanupDragSelection();
    state.selectionDrag.isDragging = true;
    state.selectionDrag.startLatLng = latlng;
    state.selectionDrag.wasMapDraggingEnabled =
      Boolean(state.leafletMap.dragging && state.leafletMap.dragging.enabled());

    if (state.leafletMap.dragging) {
      state.leafletMap.dragging.disable();
    }

    const bounds = boundsFromLatLngs(latlng, latlng);
    state.selectionDrag.rectangle = window.L.rectangle(bounds, selectionDragStyle())
      .addTo(state.leafletMap);
  }

  function updateDragSelection(latlng) {
    if (
      !state.selectionDrag.isDragging ||
      !state.selectionDrag.rectangle ||
      !state.selectionDrag.startLatLng
    ) {
      return;
    }

    const bounds = boundsFromLatLngs(state.selectionDrag.startLatLng, latlng);
    if (!bounds) {
      return;
    }
    state.selectionDrag.rectangle.setBounds(bounds);
  }

  function gridIdsIntersectingBounds(selectionBounds) {
    if (!selectionBounds) {
      return [];
    }

    const gridIds = [];
    state.gridsById.forEach((grid, gridId) => {
      const gridBounds = gridLeafletBounds(grid);
      if (gridBounds && selectionBounds.intersects(gridBounds)) {
        gridIds.push(gridId);
      }
    });

    return gridIds;
  }

  function finishDragSelection() {
    if (!state.selectionDrag.isDragging || !state.selectionDrag.rectangle) {
      cleanupDragSelection();
      return;
    }

    const selectionBounds = state.selectionDrag.rectangle.getBounds();
    const selectedGridIds = gridIdsIntersectingBounds(selectionBounds);

    cleanupDragSelection();

    if (selectedGridIds.length === 0) {
      return;
    }

    selectedGridIds.forEach((gridId) => {
      state.selectedGridIds.add(gridId);
    });
    state.selectedGridId = selectedGridIds[selectedGridIds.length - 1];
    state.selectionDrag.suppressNextClick = true;
    window.setTimeout(() => {
      state.selectionDrag.suppressNextClick = false;
    }, 200);
    renderSelectionState();
  }

  function cancelDragSelection() {
    if (!state.selectionDrag.isDragging) {
      return;
    }

    cleanupDragSelection();
    state.selectionDrag.suppressNextClick = true;
    window.setTimeout(() => {
      state.selectionDrag.suppressNextClick = false;
    }, 200);
  }

  function registerDragSelectionHandlers() {
    if (!state.leafletMap || state.leafletMap._gridDragSelectionRegistered) {
      return;
    }

    state.leafletMap._gridDragSelectionRegistered = true;
    state.leafletMap.on("mousedown", (event) => {
      if (!event.originalEvent || !event.originalEvent.shiftKey) {
        return;
      }
      if (event.originalEvent.preventDefault) {
        event.originalEvent.preventDefault();
      }
      if (event.originalEvent.stopPropagation) {
        event.originalEvent.stopPropagation();
      }

      startDragSelection(event.latlng);
    });

    state.leafletMap.on("mousemove", (event) => {
      updateDragSelection(event.latlng);
    });

    state.leafletMap.on("mouseup", () => {
      finishDragSelection();
    });

    document.addEventListener("mouseup", () => {
      if (state.selectionDrag.isDragging) {
        finishDragSelection();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") {
        return;
      }

      cancelDragSelection();
    });
  }

  function initMapPreview() {
    if (!mapPreviewElement) {
      return;
    }

    if (!leafletAvailable()) {
      setMapPreviewStatus("地図ライブラリを読み込めませんでした。", "error");
      return;
    }

    const bounds = readMapAreaBounds();
    if (!bounds) {
      setMapPreviewStatus("メモグリッド範囲を地図表示できません。", "error");
      return;
    }

    if (!state.leafletMap) {
      state.leafletMap = window.L.map(mapPreviewElement, {
        scrollWheelZoom: false,
        boxZoom: false,
        zoomSnap: 0.25,
        zoomDelta: 0.25,
      });

      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(state.leafletMap);

      registerDragSelectionHandlers();
    }

    if (state.mapAreaRectangle) {
      state.mapAreaRectangle.remove();
    }

    state.mapAreaRectangle = window.L.rectangle(bounds, {
      color: "#176f5c",
      weight: 2,
      fill: false,
      interactive: false,
    }).addTo(state.leafletMap);

    state.leafletMap.invalidateSize();
    state.leafletMap.fitBounds(bounds, {
      padding: [16, 16],
      maxZoom: 19,
    });
    setMapPreviewStatus("メモグリッド範囲を表示しています。", "success");

    window.setTimeout(() => {
      if (!state.leafletMap) {
        return;
      }
      state.leafletMap.invalidateSize();
      state.leafletMap.fitBounds(bounds, {
        padding: [16, 16],
        maxZoom: 19,
      });
    }, 0);
  }

  function clearMapGridBoundaries() {
    if (state.gridBoundaryLayer) {
      state.gridBoundaryLayer.clearLayers();
    }
    clearMapScoreLabels();
    state.mapGridRectanglesById = new Map();
  }

  function mapGridBoundaryLayer() {
    if (!state.leafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.gridBoundaryLayer) {
      state.gridBoundaryLayer = window.L.layerGroup().addTo(state.leafletMap);
    }
    return state.gridBoundaryLayer;
  }

  function mapScoreLabelLayer() {
    if (!state.leafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.scoreLabelLayer) {
      state.scoreLabelLayer = window.L.layerGroup().addTo(state.leafletMap);
    }
    return state.scoreLabelLayer;
  }

  function clearMapScoreLabels() {
    if (state.scoreLabelLayer) {
      state.scoreLabelLayer.clearLayers();
    }
  }

  function renderMapScoreLabels(grids) {
    clearMapScoreLabels();

    if (!Array.isArray(grids) || grids.length === 0) {
      return;
    }

    const labelLayer = mapScoreLabelLayer();
    if (!labelLayer) {
      return;
    }

    grids.forEach((grid) => {
      const center = gridCellCenter(grid);
      if (!center) {
        return;
      }

      window.L.marker(center, {
        interactive: false,
        keyboard: false,
        icon: window.L.divIcon({
          className: "map-score-label",
          html: `<span>${formatScoreLabel(grid.calculated_score)}</span>`,
          iconSize: [36, 22],
          iconAnchor: [18, 11],
        }),
      }).addTo(labelLayer);
    });
  }

  function renderMapGridBoundaries(grids) {
    clearMapGridBoundaries();

    if (!Array.isArray(grids) || grids.length === 0) {
      if (state.mapAreaRectangle) {
        state.mapAreaRectangle.bringToFront();
      }
      return;
    }

    initMapPreview();
    const boundaryLayer = mapGridBoundaryLayer();
    if (!boundaryLayer) {
      return;
    }

    grids.forEach((grid) => {
      const bounds = gridCellBounds(grid);
      if (!bounds) {
        return;
      }

      const gridId = Number(grid.id);
      if (!Number.isFinite(gridId)) {
        return;
      }

      const rectangle = window.L.rectangle(bounds, {
        ...mapGridRectangleStyle(grid, state.selectedGridIds.has(gridId)),
        interactive: true,
        className: "map-preview-grid-boundary",
      }).addTo(boundaryLayer);

      rectangle.on("click", (event) => {
        const originalEvent = event.originalEvent;
        if (
          state.selectionDrag.suppressNextClick ||
          (originalEvent && originalEvent.shiftKey)
        ) {
          return;
        }
        if (originalEvent && (originalEvent.ctrlKey || originalEvent.metaKey)) {
          toggleGridSelection(gridId);
          return;
        }

        selectSingleGrid(gridId);
      });
      state.mapGridRectanglesById.set(gridId, rectangle);
    });

    updateSelectedMapGridState();
    renderMapScoreLabels(grids);
  }

  function shareUsername(share) {
    if (share && share.user && share.user.username) {
      return share.user.username;
    }
    return "不明なユーザー";
  }

  function createShareItem(share) {
    const item = document.createElement("li");
    item.className = "share-list-item";

    const summary = document.createElement("span");
    summary.className = "share-summary";
    summary.textContent = `${shareUsername(share)} / share #${textOrFallback(
      share.id,
      "未設定"
    )}`;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "danger-button";
    removeButton.dataset.deleteShareId = textOrFallback(share.id, "");
    removeButton.dataset.shareUsername = shareUsername(share);
    removeButton.textContent = "共有を解除";

    item.append(summary, removeButton);
    return item;
  }

  function renderShares(shares) {
    if (!shareListElement) {
      return;
    }

    shareListElement.replaceChildren();

    if (!Array.isArray(shares) || shares.length === 0) {
      shareListElement.textContent = "共有相手はまだ登録されていません。";
      return;
    }

    const list = document.createElement("ul");
    list.className = "share-list-items";
    shares.forEach((share) => {
      list.appendChild(createShareItem(share));
    });
    shareListElement.appendChild(list);
  }

  async function loadShares(successMessage = "") {
    const currentAreaId = areaId();
    if (!shareListElement || !currentAreaId) {
      return;
    }

    setShareMessage("共有相手一覧を読み込んでいます。");
    setShareListMessage("共有相手一覧を読み込んでいます。");

    try {
      const data = await api.fetchShares(currentAreaId);
      renderShares(data && data.shares ? data.shares : []);
      if (successMessage) {
        setShareMessage(successMessage, "success");
      } else {
        setShareMessage("共有相手一覧を取得しました。");
      }
    } catch (error) {
      setShareListMessage("共有相手一覧を取得できませんでした。");
      setShareMessage(
        `共有相手一覧を取得できませんでした。${error.message}`,
        "error"
      );
    }
  }

  async function addShare() {
    const currentAreaId = areaId();
    const username = shareUsernameInput ? shareUsernameInput.value.trim() : "";
    if (!currentAreaId || !shareAddForm) {
      return;
    }
    if (!username) {
      setShareMessage("共有相手 username を入力してください。", "error");
      return;
    }

    if (shareAddSubmitButton) {
      shareAddSubmitButton.disabled = true;
    }
    setShareMessage("共有相手を追加しています。");

    try {
      await api.addShare(currentAreaId, { username });
      if (shareUsernameInput) {
        shareUsernameInput.value = "";
      }
      await loadShares("共有相手を追加しました。");
    } catch (error) {
      setShareMessage(`共有相手を追加できませんでした。${error.message}`, "error");
    } finally {
      if (shareAddSubmitButton) {
        shareAddSubmitButton.disabled = false;
      }
    }
  }

  async function deleteShare(deleteButton) {
    const currentAreaId = areaId();
    const shareId = deleteButton.dataset.deleteShareId;
    if (!currentAreaId || !shareId) {
      setShareMessage("共有解除対象の共有設定IDが見つかりません。", "error");
      return;
    }

    const confirmed = window.confirm(
      "このユーザーの共有を解除します。よろしいですか？"
    );
    if (!confirmed) {
      return;
    }

    deleteButton.disabled = true;
    setShareMessage("共有を解除しています。");

    try {
      await api.deleteShare(currentAreaId, shareId);
      await loadShares("共有を解除しました。");
    } catch (error) {
      deleteButton.disabled = false;
      setShareMessage(`共有を解除できませんでした。${error.message}`, "error");
    }
  }

  async function deleteCurrentArea() {
    if (!deleteAreaButton) {
      return;
    }

    const areaId = deleteAreaButton.dataset.areaId;
    const areaName = deleteAreaButton.dataset.areaName || "このメモグリッド";
    if (!areaId) {
      setDeleteStatus("削除対象のメモグリッドIDが見つかりません。", "error");
      return;
    }

    const confirmed = window.confirm(
      `メモグリッド「${areaName}」を削除します。関連するマス、採点、共有設定も削除されます。よろしいですか？`
    );
    if (!confirmed) {
      return;
    }

    deleteAreaButton.disabled = true;
    setDeleteStatus("メモグリッドを削除しています。");

    try {
      await api.deleteArea(areaId);
      setDeleteStatus("メモグリッドを削除しました。一覧画面へ移動します。", "success");
      window.location.href = "/maps/";
    } catch (error) {
      deleteAreaButton.disabled = false;
      setDeleteStatus(`メモグリッドを削除できませんでした。${error.message}`, "error");
    }
  }

  async function loadGridCells(options = {}) {
    const areaId = rootElement ? rootElement.dataset.areaId : "";
    if (!areaId) {
      setMessage("マス一覧を取得できませんでした。area_id が見つかりません。", "error");
      return;
    }

    setMessage("マス一覧を読み込んでいます。");
    setCount("");
    clearList();

    try {
      const data = await api.fetchGridCells(areaId);
      renderGrids(data && data.grids ? data.grids : [], options);
    } catch (error) {
      setCount("");
      clearList();
      state.selectedGridId = null;
      state.selectedGridIds = new Set();
      setSelectedGridCount(0);
      updateClearSelectedButton();
      clearMapGridBoundaries();
      setMessage(`マス一覧を取得できませんでした。${error.message}`, "error");
      setSelectedGridDetail("マス一覧を取得できなかったため、マスを選択できません。");
      setRatingFormMessage(
        "マス一覧を取得できなかったため、採点フォームは表示できません。"
      );
      setBulkRatingFormMessage(
        "マス一覧を取得できなかったため、一括採点フォームは表示できません。"
      );
    }
  }

  function readRatingForm(form) {
    const scoreInput = form.querySelector('[name="score"]');
    const commentInput = form.querySelector('[name="comment"]');
    const score = Number(scoreInput ? scoreInput.value : "");

    if (!Number.isInteger(score) || score < 1 || score > 10) {
      throw new Error("score は 1 から 10 の整数で入力してください。");
    }

    return {
      score,
      comment: commentInput ? commentInput.value : "",
    };
  }

  function readBulkRatingForm(form) {
    const gridIds = Array.from(state.selectedGridIds);
    if (gridIds.length < 2) {
      throw new Error("一括採点するには、2件以上のマスを選択してください。");
    }

    const scoreInput = form.querySelector('[name="score"]');
    const commentInput = form.querySelector('[name="comment"]');
    const score = Number(scoreInput ? scoreInput.value : "");

    if (!Number.isInteger(score) || score < 1 || score > 10) {
      throw new Error("score は 1 から 10 の整数で入力してください。");
    }

    return {
      grid_ids: gridIds,
      score,
      comment: commentInput ? commentInput.value : "",
    };
  }

  async function submitBulkRating(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    let payload;
    try {
      payload = readBulkRatingForm(form);
    } catch (error) {
      setBulkRatingFormStatus(error.message, "error");
      return;
    }

    const submittedGridIds = new Set(payload.grid_ids);
    const submittedPrimaryGridId = state.selectedGridId;

    if (submitButton) {
      submitButton.disabled = true;
    }
    setBulkRatingFormStatus("一括採点を送信しています。");

    try {
      await api.submitBulkRating(payload);
      await loadGridCells({
        selectedGridId: submittedPrimaryGridId,
        selectedGridIds: submittedGridIds,
        bulkRatingMessage: "選択中のマスを一括採点しました。",
        bulkRatingMessageType: "success",
      });
    } catch (error) {
      if (submitButton) {
        submitButton.disabled = false;
      }
      setBulkRatingFormStatus(`一括採点に失敗しました。${error.message}`, "error");
    }
  }

  async function submitRating(form) {
    const gridId = Number(form.dataset.ratingGridId);
    if (!Number.isFinite(gridId) || !state.gridsById.has(gridId)) {
      setRatingFormStatus("採点対象のマスが見つかりません。", "error");
      return;
    }

    let payload;
    try {
      payload = readRatingForm(form);
    } catch (error) {
      setRatingFormStatus(error.message, "error");
      return;
    }

    setRatingFormStatus("採点を送信しています。");

    try {
      await api.submitRating(gridId, payload);
      await loadGridCells({
        selectedGridId: gridId,
        selectedGridIds: new Set(state.selectedGridIds),
        ratingMessage: "採点しました。",
        ratingMessageType: "success",
      });
    } catch (error) {
      setRatingFormStatus(`採点に失敗しました。${error.message}`, "error");
    }
  }

  if (rootElement && messageElement && countElement && listElement) {
    listElement.addEventListener("click", (event) => {
      const selectButton = event.target.closest("[data-select-grid-id]");
      if (!selectButton) {
        return;
      }

      if (event.ctrlKey || event.metaKey) {
        toggleGridSelection(selectButton.dataset.selectGridId);
        return;
      }

      selectSingleGrid(selectButton.dataset.selectGridId);
    });

    if (clearSelectedGridsButton) {
      clearSelectedGridsButton.addEventListener("click", () => {
        clearSelectedGrids();
      });
    }

    if (selectedGridDetailElement) {
      selectedGridDetailElement.addEventListener("click", (event) => {
        const removeButton = event.target.closest("[data-remove-selected-grid-id]");
        if (!removeButton) {
          return;
        }

        removeGridSelection(removeButton.dataset.removeSelectedGridId);
      });
    }

    if (ratingFormContainer) {
      ratingFormContainer.addEventListener("submit", (event) => {
        event.preventDefault();
        const form = event.target.closest("[data-rating-grid-id]");
        if (!form) {
          return;
        }

        submitRating(form);
      });
    }

    if (bulkRatingFormContainer) {
      bulkRatingFormContainer.addEventListener("submit", (event) => {
        event.preventDefault();
        const form = event.target.closest("[data-bulk-rating-form]");
        if (!form) {
          return;
        }

        submitBulkRating(form);
      });
    }

    if (deleteAreaButton) {
      deleteAreaButton.addEventListener("click", () => {
        deleteCurrentArea();
      });
    }

    if (shareAddForm && shareListElement) {
      shareAddForm.addEventListener("submit", (event) => {
        event.preventDefault();
        addShare();
      });

      shareListElement.addEventListener("click", (event) => {
        const deleteButton = event.target.closest("[data-delete-share-id]");
        if (!deleteButton) {
          return;
        }

        deleteShare(deleteButton);
      });

      loadShares();
    }

    initMapPreview();
    loadGridCells();
  }
})();
