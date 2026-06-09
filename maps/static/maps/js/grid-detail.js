(function () {
  const rootElement = document.querySelector("#grid-detail-root");
  const messageElement = document.querySelector("#map-preview-status");
  const reloadGridCellsButton = document.querySelector("#reload-grid-cells");
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
  const gridOpacityScaleInput = document.querySelector("#grid-opacity-scale");
  const pageLoadingOverlay = document.querySelector("#site-loading-overlay");
  const defaultMapPreviewMessage = "メモグリッド範囲を表示しています。";
  const temporaryMapPreviewMessageDuration = 2200;
  const defaultOpacityScaleValue = 50;
  const minGridFillOpacityMultiplier = 0.15;
  const maxGridFillOpacityMultiplier = 1.45;
  const maxGridFillOpacity = 0.48;
  const maxSelectedGridFillOpacity = 0.58;
  let mapPreviewMessageResetTimer = null;
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
    bulkRatingMode: "same",
    leafletMap: null,
    mapAreaRectangle: null,
    gridBoundaryLayer: null,
    scoreLabelLayer: null,
    mapGridRectanglesById: new Map(),
    gridOpacityScaleValue: defaultOpacityScaleValue,
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
    if (mapPreviewMessageResetTimer) {
      window.clearTimeout(mapPreviewMessageResetTimer);
      mapPreviewMessageResetTimer = null;
    }
    messageElement.textContent = text;
    messageElement.dataset.messageType = type;
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

  function setReloadGridCellsButtonDisabled(isDisabled) {
    if (!reloadGridCellsButton) {
      return;
    }
    reloadGridCellsButton.disabled = isDisabled;
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

  function selectedMode(grids) {
    if (grids.length === 0) {
      return "none";
    }
    if (grids.length === 1) {
      return "single";
    }
    return "multiple";
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

  function createSelectedGridHeading(grid) {
    const heading = document.createElement("h3");
    heading.textContent = `マス #${textOrFallback(grid.id)}`;
    return heading;
  }

  function createSelectedGridPosition(grid) {
    const position = document.createElement("p");
    position.textContent = `行 ${displayIndex(grid.row_index)} / 列 ${displayIndex(
      grid.col_index
    )}`;
    return position;
  }

  function selectedGridRangeText(grid) {
    return [
      `north ${formatCoordinate(grid.north)}`,
      `south ${formatCoordinate(grid.south)}`,
      `east ${formatCoordinate(grid.east)}`,
      `west ${formatCoordinate(grid.west)}`,
    ].join(" / ");
  }

  function createSelectedGridDetailList(grid) {
    const detailList = document.createElement("ul");
    detailList.className = "selected-grid-cell-detail-list";
    detailList.append(
      createDetailItem("初期スコア", formatNumber(grid.initial_score)),
      createDetailItem("ユーザー平均スコア", formatNumber(grid.average_user_score)),
      createDetailItem("採点数", formatNumber(grid.rating_count)),
      createDetailItem("表示スコア", formatNumber(grid.calculated_score)),
      createDetailItem("範囲", selectedGridRangeText(grid)),
      createDetailItem("スコア更新日時", formatDateTime(grid.score_updated_at))
    );
    return detailList;
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

    selectedGridDetailElement.append(
      createSelectedGridHeading(grid),
      createSelectedGridPosition(grid),
      createSelectedGridDetailList(grid),
      createAutoScoreBreakdownSection(grid)
    );
  }

  function selectedGrids() {
    return Array.from(state.selectedGridIds)
      .map((gridId) => state.gridsById.get(gridId))
      .filter(Boolean);
  }

  function createSelectedGridSummaryItem(grid) {
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
    return item;
  }

  function renderMultipleSelectedGridSummary(grids) {
    selectedGridDetailElement.replaceChildren();

    const list = document.createElement("ul");
    list.className = "selected-grid-cell-summary-list";
    grids.forEach((grid) => {
      list.appendChild(createSelectedGridSummaryItem(grid));
    });

    selectedGridDetailElement.appendChild(list);
  }

  function renderSelectedGridSelection(grids) {
    if (!selectedGridDetailElement) {
      return;
    }

    const mode = selectedMode(grids);
    setSelectedGridCount(grids.length);
    updateClearSelectedButton();

    if (mode === "none") {
      renderSelectedGridDetail(null);
    } else if (mode === "single") {
      renderSelectedGridDetail(grids[0]);
    } else {
      renderMultipleSelectedGridSummary(grids);
    }
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

  function createRatingTarget(text) {
    const target = document.createElement("p");
    target.className = "rating-form-target";
    target.textContent = text;
    return target;
  }

  function createRatingScoreLabel() {
    const label = document.createElement("label");
    label.textContent = "スコア";
    const scoreInput = document.createElement("input");
    scoreInput.type = "number";
    scoreInput.name = "score";
    scoreInput.min = "1";
    scoreInput.max = "10";
    scoreInput.step = "1";
    scoreInput.value = "5";
    label.append(" ", scoreInput);
    return label;
  }

  function createRatingCommentLabel(placeholder) {
    const label = document.createElement("label");
    label.textContent = "コメント";
    const commentInput = document.createElement("textarea");
    commentInput.name = "comment";
    commentInput.rows = 3;
    commentInput.placeholder = placeholder;
    label.append(" ", commentInput);
    return label;
  }

  function createRatingSubmitButton(text) {
    const submitButton = document.createElement("button");
    submitButton.type = "submit";
    submitButton.textContent = text;
    return submitButton;
  }

  function createRatingStatus(datasetName, message, messageType) {
    const status = document.createElement("p");
    status.className = "rating-form-status";
    status.dataset[datasetName] = "";
    status.dataset.messageType = messageType;
    status.textContent = message;
    return status;
  }

  function createSingleRatingForm(grid, message, messageType) {
    const form = document.createElement("form");
    form.className = "rating-form";
    form.dataset.ratingGridId = textOrFallback(grid.id, "");

    form.append(
      createRatingScoreLabel(),
      createRatingCommentLabel("任意入力"),
      createRatingSubmitButton("採点する"),
      createRatingStatus("ratingFormStatus", message, messageType)
    );
    return form;
  }

  function renderSingleRatingForm(grid, message = "", messageType = "") {
    if (!ratingFormContainer) {
      return;
    }

    ratingFormContainer.replaceChildren();
    ratingFormContainer.append(
      createRatingTarget(`対象: マス #${textOrFallback(grid.id)}`),
      createSingleRatingForm(grid, message, messageType)
    );
  }

  function renderRatingFormForSelection(grids, message = "", messageType = "") {
    if (!ratingFormContainer) {
      return;
    }

    const mode = selectedMode(grids);
    if (mode === "none") {
      setRatingFormMessage("マスを選択すると、採点フォームを表示します。");
      return;
    }

    if (mode === "single") {
      renderSingleRatingForm(grids[0], message, messageType);
      return;
    }

    setRatingFormMessage(
      "複数のマスを選択中です。単体採点フォームは1件選択時のみ使用できます。"
    );
  }

  function createBulkRatingForm(message, messageType) {
    const form = document.createElement("form");
    form.className = "rating-form bulk-rating-form";
    form.dataset.bulkRatingForm = "";

    form.append(
      createRatingScoreLabel(),
      createRatingCommentLabel("任意メモ"),
      createRatingSubmitButton("一括採点する"),
      createRatingStatus("bulkRatingFormStatus", message, messageType)
    );
    return form;
  }

  function createBulkRatingModeOption(value, labelText) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "bulk-rating-mode";
    input.value = value;
    input.checked = state.bulkRatingMode === value;
    label.append(input, " ", labelText);
    return label;
  }

  function createBulkRatingModeControls() {
    const wrapper = document.createElement("div");
    wrapper.className = "bulk-rating-mode-controls";

    const heading = document.createElement("p");
    heading.textContent = "採点方式";

    const options = document.createElement("div");
    options.className = "bulk-rating-mode-options";
    options.append(
      createBulkRatingModeOption("same", "全て同じ値で採点"),
      createBulkRatingModeOption("individual", "マスごとに個別入力")
    );

    wrapper.append(heading, options);
    return wrapper;
  }

  function createIndividualRatingItem(grid) {
    const item = document.createElement("div");
    item.className = "individual-rating-item";
    item.dataset.individualRatingGridId = textOrFallback(grid.id, "");

    const summary = document.createElement("p");
    summary.className = "individual-rating-summary";
    summary.textContent = `マス #${textOrFallback(grid.id)}: ${[
      `行 ${displayIndex(grid.row_index)}`,
      `列 ${displayIndex(grid.col_index)}`,
      `表示スコア ${formatNumber(grid.calculated_score)}`,
    ].join(" / ")}`;

    const scoreLabel = createRatingScoreLabel();
    const scoreInput = scoreLabel.querySelector('[name="score"]');
    if (scoreInput) {
      scoreInput.dataset.individualRatingScore = "";
    }

    const commentLabel = createRatingCommentLabel("任意入力");
    const commentInput = commentLabel.querySelector('[name="comment"]');
    if (commentInput) {
      commentInput.dataset.individualRatingComment = "";
    }

    item.append(summary, scoreLabel, commentLabel);
    return item;
  }

  function createIndividualBulkRatingForm(grids, message, messageType) {
    const form = document.createElement("form");
    form.className = "rating-form individual-bulk-rating-form";
    form.dataset.individualBulkRatingForm = "";

    const list = document.createElement("div");
    list.className = "individual-rating-list";
    grids.forEach((grid) => {
      list.appendChild(createIndividualRatingItem(grid));
    });

    form.append(
      list,
      createRatingSubmitButton("個別採点を送信"),
      createRatingStatus("bulkRatingFormStatus", message, messageType)
    );
    return form;
  }

  function renderBulkRatingFormForSelection(grids, message = "", messageType = "") {
    if (!bulkRatingFormContainer) {
      return;
    }

    bulkRatingFormContainer.replaceChildren();

    if (selectedMode(grids) !== "multiple") {
      bulkRatingFormContainer.textContent =
        "複数のマスを選択すると、一括採点フォームを表示します。";
      return;
    }

    bulkRatingFormContainer.append(
      createRatingTarget(`対象: ${grids.length}件のマス`),
      createBulkRatingModeControls(),
      state.bulkRatingMode === "individual"
        ? createIndividualBulkRatingForm(grids, message, messageType)
        : createBulkRatingForm(message, messageType)
    );
  }

  function gridScoreStyle(grid) {
    const rawScore = grid ? grid.calculated_score : undefined;

    if (rawScore === null || rawScore === undefined || rawScore === "") {
      return {
        color: "#8a94a1",
        fillColor: "#e5e7eb",
        fillOpacity: 0.12,
      };
    }

    const score = Number(rawScore);

    if (!Number.isFinite(score)) {
      return {
        color: "#8a94a1",
        fillColor: "#e5e7eb",
        fillOpacity: 0.12,
      };
    }

    if (score < 3) {
      return {
        color: "#b84a4a",
        fillColor: "#f3b6b6",
        fillOpacity: 0.32,
      };
    }
    if (score < 6) {
      return {
        color: "#d08a2f",
        fillColor: "#f8c878",
        fillOpacity: 0.32,
      };
    }
    if (score < 8) {
      return {
        color: "#8da63a",
        fillColor: "#cfe887",
        fillOpacity: 0.32,
      };
    }

    return {
      color: "#176f5c",
      fillColor: "#86d9b3",
      fillOpacity: 0.32,
    };
  }

  function gridFillOpacityMultiplier() {
    const normalizedValue = Math.min(
      Math.max(Number(state.gridOpacityScaleValue), 0),
      100
    );
    if (normalizedValue <= defaultOpacityScaleValue) {
      return minGridFillOpacityMultiplier
        + (normalizedValue / defaultOpacityScaleValue)
        * (1 - minGridFillOpacityMultiplier);
    }
    return 1
      + ((normalizedValue - defaultOpacityScaleValue) / defaultOpacityScaleValue)
      * (maxGridFillOpacityMultiplier - 1);
  }

  function scaledGridFillOpacity(baseOpacity, isSelected) {
    const scaledOpacity = baseOpacity * gridFillOpacityMultiplier();
    const selectedOpacity = isSelected ? scaledOpacity + 0.12 : scaledOpacity;
    const maxOpacity = isSelected ? maxSelectedGridFillOpacity : maxGridFillOpacity;
    return Math.min(selectedOpacity, maxOpacity);
  }

  function scoreLabelToneClass(value) {
    if (value === null || value === undefined || value === "") {
      return "map-score-label--unknown";
    }

    const score = Number(value);
    if (!Number.isFinite(score)) {
      return "map-score-label--unknown";
    }

    if (score < 3) {
      return "map-score-label--low";
    }
    if (score < 6) {
      return "map-score-label--middle";
    }
    if (score < 8) {
      return "map-score-label--high";
    }
    return "map-score-label--very-high";
  }

  function mapGridRectangleStyle(grid, isSelected) {
    const scoreStyle = gridScoreStyle(grid);

    return {
      color: scoreStyle.color,
      weight: isSelected ? 4 : 1,
      opacity: isSelected ? 1 : 0.72,
      fill: true,
      fillColor: scoreStyle.fillColor,
      fillOpacity: scaledGridFillOpacity(scoreStyle.fillOpacity, isSelected),
    };
  }

  function selectedMapGridStyle(gridId, grid) {
    return mapGridRectangleStyle(grid, state.selectedGridIds.has(gridId));
  }

  function applyGridRectangleStyle(grid, rectangle, isSelected) {
    rectangle.setStyle(mapGridRectangleStyle(grid, isSelected));
  }

  function bringMapAreaRectangleToFront() {
    if (state.mapAreaRectangle) {
      state.mapAreaRectangle.bringToFront();
    }
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

    bringMapAreaRectangleToFront();
  }

  function readGridOpacityScaleValue() {
    if (!gridOpacityScaleInput) {
      return defaultOpacityScaleValue;
    }
    const inputValue = Number(gridOpacityScaleInput.value);
    if (!Number.isFinite(inputValue)) {
      return defaultOpacityScaleValue;
    }
    return Math.min(Math.max(inputValue, 0), 100);
  }

  function updateGridOpacityScale() {
    state.gridOpacityScaleValue = readGridOpacityScaleValue();
    updateSelectedMapGridState();
  }

  function renderSelectionState(
    message = "",
    messageType = "",
    bulkMessage = "",
    bulkMessageType = ""
  ) {
    const grids = selectedGrids();
    renderSelectedGridSelection(grids);
    renderRatingFormForSelection(grids, message, messageType);
    renderBulkRatingFormForSelection(grids, bulkMessage, bulkMessageType);
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

  function resetGridStateForRender() {
    state.gridsById = new Map();
    state.selectedGridId = null;
    state.selectedGridIds = new Set();
  }

  function renderEmptyGridList() {
    setMessage("このメモグリッドには、まだグリッドがありません。");
    setSelectedGridDetail("表示できるマスがありません。");
    setRatingFormMessage("表示できるマスがないため、採点フォームは表示できません。");
    setBulkRatingFormMessage(
      "表示できるマスがないため、一括採点フォームは表示できません。"
    );
    setSelectedGridCount(0);
    updateClearSelectedButton();
    clearMapGridBoundaries();
  }

  function renderGridListLoadError(error) {
    resetGridStateForRender();
    setSelectedGridCount(0);
    updateClearSelectedButton();
    clearMapGridBoundaries();
    setMessage(`グリッドを取得できませんでした。${error.message}`, "error");
    setSelectedGridDetail("グリッドを取得できなかったため、マスを選択できません。");
    setRatingFormMessage(
      "グリッドを取得できなかったため、採点フォームは表示できません。"
    );
    setBulkRatingFormMessage(
      "グリッドを取得できなかったため、一括採点フォームは表示できません。"
    );
  }

  function gridMapById(grids) {
    return new Map(grids.map((grid) => [Number(grid.id), grid]));
  }

  function requestedGridSelection(options, previousSelectedGridIds) {
    if (options.selectedGridIds) {
      return new Set(Array.from(options.selectedGridIds).map(Number));
    }
    if (options.selectedGridId) {
      return new Set([Number(options.selectedGridId)]);
    }
    return previousSelectedGridIds;
  }

  function restoreSelectedGridState(
    options,
    previousSelectedGridIds,
    previousSelectedGridId
  ) {
    const requestedSelectedGridIds = requestedGridSelection(
      options,
      previousSelectedGridIds
    );
    state.selectedGridIds = new Set(
      Array.from(requestedSelectedGridIds).filter((gridId) =>
        state.gridsById.has(gridId)
      )
    );

    if (
      options.selectedGridId &&
      state.selectedGridIds.has(Number(options.selectedGridId))
    ) {
      state.selectedGridId = Number(options.selectedGridId);
    } else if (state.selectedGridIds.size === 1) {
      state.selectedGridId = Array.from(state.selectedGridIds)[0];
    } else if (state.selectedGridIds.size > 1) {
      const remainingPreviousTarget = Number(previousSelectedGridId);
      state.selectedGridId = state.selectedGridIds.has(remainingPreviousTarget)
        ? remainingPreviousTarget
        : Array.from(state.selectedGridIds)[state.selectedGridIds.size - 1];
    }
  }

  function renderGrids(grids, options = {}) {
    const previousSelectedGridIds = new Set(state.selectedGridIds);
    const previousSelectedGridId = state.selectedGridId;
    resetGridStateForRender();

    if (!Array.isArray(grids) || grids.length === 0) {
      renderEmptyGridList();
      return;
    }

    state.gridsById = gridMapById(grids);
    restoreSelectedGridState(
      options,
      previousSelectedGridIds,
      previousSelectedGridId
    );
    renderMapGridBoundaries(grids);
    renderSelectionState(
      options.ratingMessage || "",
      options.ratingMessageType || "",
      options.bulkRatingMessage || "",
      options.bulkRatingMessageType || ""
    );

    if (options.reloadMessage) {
      setTemporaryMapPreviewStatus(
        options.reloadMessage,
        options.reloadMessageType || "success"
      );
    }
  }

  function areaId() {
    return rootElement ? rootElement.dataset.areaId : "";
  }

  function setMapPreviewStatus(text, type = "") {
    if (!mapPreviewStatusElement) {
      return;
    }
    if (mapPreviewMessageResetTimer) {
      window.clearTimeout(mapPreviewMessageResetTimer);
      mapPreviewMessageResetTimer = null;
    }
    mapPreviewStatusElement.textContent = text;
    mapPreviewStatusElement.dataset.messageType = type;
  }

  function setTemporaryMapPreviewStatus(text, type = "") {
    setMapPreviewStatus(text, type);
    mapPreviewMessageResetTimer = window.setTimeout(() => {
      mapPreviewMessageResetTimer = null;
      setMapPreviewStatus(defaultMapPreviewMessage, "success");
    }, temporaryMapPreviewMessageDuration);
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

  function createLeafletMap() {
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

    state.leafletMap.on("zoomend", updateMapScoreLabelSize);
    registerDragSelectionHandlers();
  }

  function ensureLeafletMap() {
    if (!state.leafletMap) {
      createLeafletMap();
    }
  }

  function drawMapAreaRectangle(bounds) {
    if (state.mapAreaRectangle) {
      state.mapAreaRectangle.remove();
    }

    state.mapAreaRectangle = window.L.rectangle(bounds, {
      color: "#176f5c",
      weight: 2,
      fill: false,
      interactive: false,
    }).addTo(state.leafletMap);
  }

  function fitMapAreaBounds(bounds) {
    state.leafletMap.invalidateSize();
    state.leafletMap.fitBounds(bounds, {
      padding: [16, 16],
      maxZoom: 19,
    });
  }

  function scheduleMapAreaRefit(bounds) {
    window.setTimeout(() => {
      if (!state.leafletMap) {
        return;
      }
      fitMapAreaBounds(bounds);
      updateMapScoreLabelSize();
    }, 0);
  }

  function scoreLabelSizeClass(zoom) {
    if (!Number.isFinite(zoom)) {
      return "is-medium-score-label";
    }
    if (zoom <= 13) {
      return "is-small-score-label";
    }
    if (zoom >= 17) {
      return "is-large-score-label";
    }
    return "is-medium-score-label";
  }

  function updateMapScoreLabelSize() {
    if (!state.leafletMap || !mapPreviewElement) {
      return;
    }

    const sizeClass = scoreLabelSizeClass(state.leafletMap.getZoom());
    mapPreviewElement.classList.toggle(
      "is-small-score-label",
      sizeClass === "is-small-score-label"
    );
    mapPreviewElement.classList.toggle(
      "is-medium-score-label",
      sizeClass === "is-medium-score-label"
    );
    mapPreviewElement.classList.toggle(
      "is-large-score-label",
      sizeClass === "is-large-score-label"
    );
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

    ensureLeafletMap();
    drawMapAreaRectangle(bounds);
    fitMapAreaBounds(bounds);
    updateMapScoreLabelSize();
    setMapPreviewStatus(defaultMapPreviewMessage, "success");
    scheduleMapAreaRefit(bounds);
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

  function createMapScoreLabel(grid, center) {
    return window.L.marker(center, {
      interactive: false,
      keyboard: false,
      icon: window.L.divIcon({
        className: `map-score-label ${scoreLabelToneClass(grid.calculated_score)}`,
        html: `<span>${formatScoreLabel(grid.calculated_score)}</span>`,
        iconSize: [36, 22],
        iconAnchor: [18, 11],
      }),
    });
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

      createMapScoreLabel(grid, center).addTo(labelLayer);
    });
    updateMapScoreLabelSize();
  }

  function gridIdForMap(grid) {
    const gridId = Number(grid.id);
    return Number.isFinite(gridId) ? gridId : null;
  }

  function handleMapGridClick(gridId, event) {
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
  }

  function createMapGridRectangle(grid, gridId, bounds) {
    const rectangle = window.L.rectangle(bounds, {
      ...selectedMapGridStyle(gridId, grid),
      interactive: true,
      className: "map-preview-grid-boundary",
    });

    rectangle.on("click", (event) => {
      handleMapGridClick(gridId, event);
    });

    return rectangle;
  }

  function renderMapGridBoundary(grid, boundaryLayer) {
    const bounds = gridCellBounds(grid);
    if (!bounds) {
      return;
    }

    const gridId = gridIdForMap(grid);
    if (gridId === null) {
      return;
    }

    const rectangle = createMapGridRectangle(grid, gridId, bounds).addTo(
      boundaryLayer
    );
    state.mapGridRectanglesById.set(gridId, rectangle);
  }

  function renderMapGridBoundaries(grids) {
    clearMapGridBoundaries();

    if (!Array.isArray(grids) || grids.length === 0) {
      bringMapAreaRectangleToFront();
      return;
    }

    initMapPreview();
    const boundaryLayer = mapGridBoundaryLayer();
    if (!boundaryLayer) {
      return;
    }

    grids.forEach((grid) => {
      renderMapGridBoundary(grid, boundaryLayer);
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
    summary.textContent = `${shareUsername(share)} / 共有ID: ${textOrFallback(
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
      setShareMessage("共有相手のユーザー名を入力してください。", "error");
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
      setMessage("グリッドを取得できませんでした。area_id が見つかりません。", "error");
      return;
    }

    if (!options.keepCurrentMapPreviewMessage) {
      setMessage("グリッドを読み込んでいます。");
    }
    setReloadGridCellsButtonDisabled(true);

    try {
      const data = await api.fetchGridCells(areaId);
      renderGrids(data && data.grids ? data.grids : [], options);
    } catch (error) {
      renderGridListLoadError(error);
    } finally {
      setReloadGridCellsButtonDisabled(false);
    }
  }

  function reloadGridCells() {
    loadGridCells({
      selectedGridId: state.selectedGridId,
      selectedGridIds: new Set(state.selectedGridIds),
      reloadMessage: "グリッドを再取得しました。",
      reloadMessageType: "success",
      keepCurrentMapPreviewMessage: true,
    });
  }

  function readRatingForm(form) {
    const scoreInput = form.querySelector('[name="score"]');
    const commentInput = form.querySelector('[name="comment"]');
    const score = Number(scoreInput ? scoreInput.value : "");

    if (!Number.isInteger(score) || score < 1 || score > 10) {
      throw new Error("スコアは 1 から 10 の整数で入力してください。");
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
      throw new Error("スコアは 1 から 10 の整数で入力してください。");
    }

    return {
      grid_ids: gridIds,
      score,
      comment: commentInput ? commentInput.value : "",
    };
  }

  function readIndividualBulkRatingForm(form) {
    const items = Array.from(form.querySelectorAll("[data-individual-rating-grid-id]"));
    if (items.length < 2) {
      throw new Error("個別採点するには、2件以上のマスを選択してください。");
    }

    return items.map((item) => {
      const gridId = Number(item.dataset.individualRatingGridId);
      const scoreInput = item.querySelector("[data-individual-rating-score]");
      const commentInput = item.querySelector("[data-individual-rating-comment]");
      const score = Number(scoreInput ? scoreInput.value : "");

      if (!Number.isFinite(gridId) || !state.gridsById.has(gridId)) {
        throw new Error("採点対象のマスが見つかりません。");
      }
      if (!Number.isInteger(score) || score < 1 || score > 10) {
        throw new Error(`マス #${gridId} のスコアは 1 から 10 の整数で入力してください。`);
      }

      return {
        gridId,
        payload: {
          score,
          comment: commentInput ? commentInput.value : "",
        },
      };
    });
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
    showPageLoading();

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
    } finally {
      hidePageLoading();
    }
  }

  async function submitIndividualBulkRating(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    let ratings;
    try {
      ratings = readIndividualBulkRatingForm(form);
    } catch (error) {
      setBulkRatingFormStatus(error.message, "error");
      return;
    }

    const submittedGridIds = new Set(ratings.map((rating) => rating.gridId));
    const submittedPrimaryGridId = state.selectedGridId;
    const failures = [];
    let successCount = 0;

    if (submitButton) {
      submitButton.disabled = true;
    }
    setBulkRatingFormStatus("個別採点を送信しています。");
    showPageLoading();

    for (const rating of ratings) {
      try {
        await api.submitRating(rating.gridId, rating.payload);
        successCount += 1;
      } catch (error) {
        failures.push({ gridId: rating.gridId, message: error.message });
      }
    }

    const failedCount = failures.length;
    const firstFailure = failures[0];
    const message = failedCount === 0
      ? "選択中のマスを個別採点しました。"
      : successCount > 0
        ? `${successCount}件の採点に成功し、${failedCount}件の採点に失敗しました。`
        : `個別採点に失敗しました。${firstFailure ? firstFailure.message : ""}`;
    const messageType = failedCount === 0 ? "success" : "error";

    try {
      await loadGridCells({
        selectedGridId: submittedPrimaryGridId,
        selectedGridIds: submittedGridIds,
        bulkRatingMessage: message,
        bulkRatingMessageType: messageType,
      });
    } catch (error) {
      setBulkRatingFormStatus(error.message, "error");
    } finally {
      hidePageLoading();
      if (submitButton) {
        submitButton.disabled = false;
      }
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
    showPageLoading();

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
    } finally {
      hidePageLoading();
    }
  }

  if (rootElement && messageElement) {
    if (clearSelectedGridsButton) {
      clearSelectedGridsButton.addEventListener("click", () => {
        clearSelectedGrids();
      });
    }

    if (reloadGridCellsButton) {
      reloadGridCellsButton.addEventListener("click", () => {
        reloadGridCells();
      });
    }

    if (gridOpacityScaleInput) {
      state.gridOpacityScaleValue = readGridOpacityScaleValue();
      gridOpacityScaleInput.addEventListener("input", updateGridOpacityScale);
      gridOpacityScaleInput.addEventListener("change", updateGridOpacityScale);
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
      bulkRatingFormContainer.addEventListener("change", (event) => {
        if (!event.target.matches('[name="bulk-rating-mode"]')) {
          return;
        }

        state.bulkRatingMode = event.target.value;
        renderSelectionState();
      });

      bulkRatingFormContainer.addEventListener("submit", (event) => {
        event.preventDefault();
        const individualForm = event.target.closest("[data-individual-bulk-rating-form]");
        if (individualForm) {
          submitIndividualBulkRating(individualForm);
          return;
        }

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
