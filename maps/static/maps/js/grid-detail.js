(function () {
  // メモグリッド詳細画面の地図描画、GridCell選択、採点UI、共有相手管理を担当する。
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
  const mapPreviewZoomOutButton = document.querySelector("#map-preview-zoom-out");
  const mapPreviewZoomInButton = document.querySelector("#map-preview-zoom-in");
  const mapPreviewFitBoundsButton = document.querySelector(
    "#map-preview-fit-bounds"
  );
  const expandMapPreviewButton = document.querySelector("#expand-map-preview");
  const expandedMapModalElement = document.querySelector("#expanded-map-modal");
  const expandedMapPreviewElement = document.querySelector("#expanded-map-preview");
  const closeExpandedMapButton = document.querySelector("#close-expanded-map");
  const expandedMapZoomOutButton = document.querySelector("#expanded-map-zoom-out");
  const expandedMapZoomInButton = document.querySelector("#expanded-map-zoom-in");
  const expandedMapFitBoundsButton = document.querySelector(
    "#expanded-map-fit-bounds"
  );
  const gridOpacityScaleInput = document.querySelector("#grid-opacity-scale");
  const gridOpacityScaleValueElement = document.querySelector(
    "#grid-opacity-scale-value"
  );
  const scoreLabelToggleInput = document.querySelector("#score-label-toggle");
  const ratedGridToggleInput = document.querySelector("#rated-grid-toggle");
  const pageLoadingOverlay = document.querySelector("#site-loading-overlay");
  const defaultMapPreviewMessage = "メモグリッド範囲を表示しています。";
  const temporaryMapPreviewMessageDuration = 2200;
  const defaultOpacityScaleValue = 50;
  const minGridFillOpacityMultiplier = 0.15;
  const maxGridFillOpacityMultiplier = 1.65;
  const maxGridFillOpacity = 0.54;
  const maxSelectedGridFillOpacity = 0.64;
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
    leafletMap: null,
    expandedLeafletMap: null,
    mapAreaRectangle: null,
    expandedMapAreaRectangle: null,
    gridBoundaryLayer: null,
    expandedGridBoundaryLayer: null,
    scoreLabelLayer: null,
    expandedScoreLabelLayer: null,
    ratedGridMarkerLayer: null,
    expandedRatedGridMarkerLayer: null,
    mapGridRectanglesById: new Map(),
    expandedMapGridRectanglesById: new Map(),
    gridOpacityScaleValue: defaultOpacityScaleValue,
    scoreLabelsVisible: true,
    ratedGridMarkersVisible: false,
    documentDragSelectionHandlersRegistered: false,
    normalSelectionDrag: {
      isDragging: false,
      startLatLng: null,
      rectangle: null,
      wasMapDraggingEnabled: true,
      suppressNextClick: false,
    },
    expandedSelectionDrag: {
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
    ratingFormContainer.hidden = false;
    ratingFormContainer.textContent = text;
  }

  function setBulkRatingFormMessage(text) {
    if (!bulkRatingFormContainer) {
      return;
    }
    bulkRatingFormContainer.textContent = text;
  }

  function showRatingPanel(panelName) {
    if (ratingFormContainer) {
      ratingFormContainer.hidden = panelName === "bulk";
    }
    if (bulkRatingFormContainer) {
      bulkRatingFormContainer.hidden = panelName !== "bulk";
    }
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
    const section = document.createElement("details");
    section.className = "selected-grid-panel-details auto-score-breakdown-section";

    const heading = document.createElement("summary");
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

    // 点数だけでは判断理由が見えないため、主な加点・減点要因を折りたたんで表示する。
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
      createDetailItem(
        "位置",
        `行 ${displayIndex(grid.row_index)} / 列 ${displayIndex(grid.col_index)}`
      ),
      createDetailItem("初期スコア", formatNumber(grid.initial_score)),
      createDetailItem("ユーザー平均スコア", formatNumber(grid.average_user_score)),
      createDetailItem("採点数", formatNumber(grid.rating_count)),
      createDetailItem("表示スコア", formatNumber(grid.calculated_score)),
      createDetailItem("範囲", selectedGridRangeText(grid)),
      createDetailItem("スコア更新日時", formatDateTime(grid.score_updated_at))
    );
    return detailList;
  }

  function createSelectedGridDetailDetails(grid) {
    const details = document.createElement("details");
    details.className = "selected-grid-panel-details";

    const summary = document.createElement("summary");
    summary.textContent = "グリッド詳細";

    details.append(summary, createSelectedGridDetailList(grid));
    return details;
  }

  function gridCommentText(grid) {
    // APIの変遷に備え、既知のコメント候補を拾って表示側の互換性を保つ。
    const commentCandidates = [
      grid.comment,
      grid.rating_comment,
      grid.user_comment,
      grid.current_user_comment,
      grid.my_comment,
      grid.latest_comment,
      grid.rating?.comment,
      grid.current_user_rating?.comment,
      grid.my_rating?.comment,
    ];
    const comment = commentCandidates.find(
      (value) =>
        value !== null &&
        value !== undefined &&
        String(value).trim() !== ""
    );
    return comment ? String(comment).trim() : "コメントなし";
  }

  function createGridCommentDetails(grid) {
    const details = document.createElement("details");
    details.className = "selected-grid-panel-details selected-grid-comment-details";

    const summary = document.createElement("summary");
    summary.textContent = "コメント";

    const commentText = document.createElement("p");
    commentText.className = "selected-grid-comment-text";
    commentText.textContent = gridCommentText(grid);

    details.append(summary, commentText);
    return details;
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
      createSelectedGridDetailDetails(grid),
      createGridCommentDetails(grid),
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
    summary.textContent = `#${textOrFallback(grid.id)}: ${[
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

    const commentNote = document.createElement("p");
    commentNote.className = "selected-grid-comment-note";
    commentNote.textContent = "コメントは1件選択時に表示します。";

    const list = document.createElement("ul");
    list.className = "selected-grid-cell-summary-list";
    grids.forEach((grid) => {
      list.appendChild(createSelectedGridSummaryItem(grid));
    });

    selectedGridDetailElement.append(commentNote, list);
  }

  function renderSelectedGridSelection(grids) {
    if (!selectedGridDetailElement) {
      return;
    }

    const mode = selectedMode(grids);
    setSelectedGridCount(grids.length);
    updateClearSelectedButton();

    // 選択数に応じて、未選択案内・単体詳細・複数選択一覧を切り替える。
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
      showRatingPanel("single");
      setRatingFormMessage("地図上のグリッドをクリックして選択してください。");
      return;
    }

    // 単体選択ではコメント付きで1マスを採点し、複数選択時は一括採点UIへ譲る。
    if (mode === "single") {
      showRatingPanel("single");
      renderSingleRatingForm(grids[0], message, messageType);
      return;
    }

    ratingFormContainer.replaceChildren();
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

  function renderBulkRatingFormForSelection(grids, message = "", messageType = "") {
    if (!bulkRatingFormContainer) {
      return;
    }

    bulkRatingFormContainer.replaceChildren();

    if (selectedMode(grids) !== "multiple") {
      bulkRatingFormContainer.hidden = true;
      return;
    }

    // 複数選択時は同じスコアをまとめて送れるようにして入力の手間を減らす。
    showRatingPanel("bulk");
    bulkRatingFormContainer.append(
      createRatingTarget(`対象: ${grids.length}件のマス`),
      createBulkRatingForm(message, messageType)
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

    // calculated_score を色に変換し、地図だけで傾向をざっと読めるようにする。
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

  function bringExpandedMapAreaRectangleToFront() {
    if (state.expandedMapAreaRectangle) {
      state.expandedMapAreaRectangle.bringToFront();
    }
  }

  function updateSelectedMapGridState() {
    // 通常地図と拡大地図は同じ選択集合を共有し、どちらで選んでも見た目を同期する。
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

    if (expandedMapIsOpen()) {
      state.expandedMapGridRectanglesById.forEach((rectangle, gridId) => {
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

      bringExpandedMapAreaRectangleToFront();
    }
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

  function updateGridOpacityScaleValueText() {
    if (!gridOpacityScaleValueElement) {
      return;
    }
    gridOpacityScaleValueElement.textContent = String(state.gridOpacityScaleValue);
  }

  function updateGridOpacityScale() {
    state.gridOpacityScaleValue = readGridOpacityScaleValue();
    updateGridOpacityScaleValueText();
    updateSelectedMapGridState();
  }

  function renderSelectionState(
    message = "",
    messageType = "",
    bulkMessage = "",
    bulkMessageType = ""
  ) {
    const grids = selectedGrids();
    // 選択状態は詳細欄・採点フォーム・地図スタイルの3か所に同時反映する。
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
    showRatingPanel("single");
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
    showRatingPanel("single");
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
    // 採点後や再取得後も、残っているGridCellだけ選択状態を復元する。
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

    // APIから取得したGridCellを、地図・選択欄・採点欄の共通データとして持つ。
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

  function boundsCenter(bounds) {
    if (!Array.isArray(bounds) || bounds.length !== 2) {
      return null;
    }

    const south = Number(bounds[0][0]);
    const west = Number(bounds[0][1]);
    const north = Number(bounds[1][0]);
    const east = Number(bounds[1][1]);

    if (
      !Number.isFinite(north) ||
      !Number.isFinite(south) ||
      !Number.isFinite(east) ||
      !Number.isFinite(west)
    ) {
      return null;
    }

    return [
      (north + south) / 2,
      (east + west) / 2,
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

  function cleanupDragSelection(leafletMap, dragState) {
    if (dragState.rectangle) {
      dragState.rectangle.remove();
    }

    if (
      leafletMap &&
      leafletMap.dragging &&
      dragState.wasMapDraggingEnabled
    ) {
      leafletMap.dragging.enable();
    }

    dragState.isDragging = false;
    dragState.startLatLng = null;
    dragState.rectangle = null;
    dragState.wasMapDraggingEnabled = true;
  }

  function startDragSelection(leafletMap, dragState, latlng) {
    if (!leafletMap || !leafletAvailable() || !latlng) {
      return;
    }

    cleanupDragSelection(leafletMap, dragState);
    dragState.isDragging = true;
    dragState.startLatLng = latlng;
    dragState.wasMapDraggingEnabled =
      Boolean(leafletMap.dragging && leafletMap.dragging.enabled());

    if (leafletMap.dragging) {
      leafletMap.dragging.disable();
    }

    // Shiftドラッグ中は地図移動より範囲選択を優先し、連続したマスをまとめて選ぶ。
    const bounds = boundsFromLatLngs(latlng, latlng);
    dragState.rectangle = window.L.rectangle(bounds, selectionDragStyle())
      .addTo(leafletMap);
  }

  function updateDragSelection(dragState, latlng) {
    if (
      !dragState.isDragging ||
      !dragState.rectangle ||
      !dragState.startLatLng
    ) {
      return;
    }

    const bounds = boundsFromLatLngs(dragState.startLatLng, latlng);
    if (!bounds) {
      return;
    }
    dragState.rectangle.setBounds(bounds);
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

  function suppressDragClick(dragState) {
    dragState.suppressNextClick = true;
    window.setTimeout(() => {
      dragState.suppressNextClick = false;
    }, 200);
  }

  function finishDragSelection(leafletMap, dragState) {
    if (!dragState.isDragging || !dragState.rectangle) {
      cleanupDragSelection(leafletMap, dragState);
      return;
    }

    const selectionBounds = dragState.rectangle.getBounds();
    const selectedGridIds = gridIdsIntersectingBounds(selectionBounds);

    cleanupDragSelection(leafletMap, dragState);

    if (selectedGridIds.length === 0) {
      return;
    }

    // 範囲内のマスは一括採点の候補として選択集合へ追加する。
    selectedGridIds.forEach((gridId) => {
      state.selectedGridIds.add(gridId);
    });
    state.selectedGridId = selectedGridIds[selectedGridIds.length - 1];
    suppressDragClick(dragState);
    renderSelectionState();
  }

  function cancelDragSelection(leafletMap, dragState) {
    if (!dragState.isDragging) {
      return;
    }

    cleanupDragSelection(leafletMap, dragState);
    suppressDragClick(dragState);
  }

  function registerDragSelectionHandlers(leafletMap, dragState) {
    if (!leafletMap || leafletMap._gridDragSelectionRegistered) {
      return;
    }

    leafletMap._gridDragSelectionRegistered = true;
    leafletMap.on("mousedown", (event) => {
      if (!event.originalEvent || !event.originalEvent.shiftKey) {
        return;
      }
      if (event.originalEvent.preventDefault) {
        event.originalEvent.preventDefault();
      }
      if (event.originalEvent.stopPropagation) {
        event.originalEvent.stopPropagation();
      }

      startDragSelection(leafletMap, dragState, event.latlng);
    });

    leafletMap.on("mousemove", (event) => {
      updateDragSelection(dragState, event.latlng);
    });

    leafletMap.on("mouseup", () => {
      finishDragSelection(leafletMap, dragState);
    });
  }

  function finishActiveDragSelections() {
    if (state.normalSelectionDrag.isDragging) {
      finishDragSelection(state.leafletMap, state.normalSelectionDrag);
    }
    if (state.expandedSelectionDrag.isDragging) {
      finishDragSelection(state.expandedLeafletMap, state.expandedSelectionDrag);
    }
  }

  function cancelActiveDragSelections() {
    cancelDragSelection(state.leafletMap, state.normalSelectionDrag);
    cancelDragSelection(state.expandedLeafletMap, state.expandedSelectionDrag);
  }

  function registerDocumentDragSelectionHandlers() {
    if (state.documentDragSelectionHandlersRegistered) {
      return;
    }

    state.documentDragSelectionHandlersRegistered = true;
    document.addEventListener("mouseup", finishActiveDragSelections);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        cancelActiveDragSelections();
      }
    });
  }

  function createBaseLeafletMap(element) {
    // 通常地図と拡大地図で同じLeaflet設定を使い、操作感と描画を揃える。
    const leafletMap = window.L.map(element, {
      scrollWheelZoom: false,
      boxZoom: false,
      zoomSnap: 0.25,
      zoomDelta: 0.25,
    });

    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(leafletMap);

    return leafletMap;
  }

  function createLeafletMap() {
    state.leafletMap = createBaseLeafletMap(mapPreviewElement);
    state.leafletMap.on("zoomend", updateMapScoreLabelSize);
    registerDragSelectionHandlers(state.leafletMap, state.normalSelectionDrag);
    registerDocumentDragSelectionHandlers();
  }

  function ensureLeafletMap() {
    if (!state.leafletMap) {
      createLeafletMap();
    }
  }

  function createExpandedLeafletMap() {
    state.expandedLeafletMap = createBaseLeafletMap(expandedMapPreviewElement);
    state.expandedLeafletMap.on("zoomend", updateExpandedMapScoreLabelSize);
    registerDragSelectionHandlers(
      state.expandedLeafletMap,
      state.expandedSelectionDrag
    );
    registerDocumentDragSelectionHandlers();
  }

  function ensureExpandedLeafletMap() {
    if (!expandedMapPreviewElement || !leafletAvailable()) {
      return;
    }
    if (!state.expandedLeafletMap) {
      createExpandedLeafletMap();
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

  function updateScoreLabelSizeForMap(leafletMap, mapElement) {
    if (!leafletMap || !mapElement) {
      return;
    }

    const sizeClass = scoreLabelSizeClass(leafletMap.getZoom());
    mapElement.classList.toggle(
      "is-small-score-label",
      sizeClass === "is-small-score-label"
    );
    mapElement.classList.toggle(
      "is-medium-score-label",
      sizeClass === "is-medium-score-label"
    );
    mapElement.classList.toggle(
      "is-large-score-label",
      sizeClass === "is-large-score-label"
    );
  }

  function updateMapScoreLabelSize() {
    updateScoreLabelSizeForMap(state.leafletMap, mapPreviewElement);
  }

  function updateExpandedMapScoreLabelSize() {
    updateScoreLabelSizeForMap(
      state.expandedLeafletMap,
      expandedMapPreviewElement
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
    // 詳細画面ではまずMapArea全体を見せ、そこにGridCellを重ねていく。
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
    clearRatedGridMarkers();
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

  function mapRatedGridMarkerLayer() {
    if (!state.leafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.ratedGridMarkerLayer) {
      state.ratedGridMarkerLayer = window.L.layerGroup().addTo(state.leafletMap);
    }
    return state.ratedGridMarkerLayer;
  }

  function clearRatedGridMarkers() {
    if (state.ratedGridMarkerLayer) {
      state.ratedGridMarkerLayer.clearLayers();
    }
  }

  function expandedMapGridBoundaryLayer() {
    if (!state.expandedLeafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.expandedGridBoundaryLayer) {
      state.expandedGridBoundaryLayer = window.L.layerGroup().addTo(
        state.expandedLeafletMap
      );
    }
    return state.expandedGridBoundaryLayer;
  }

  function expandedMapScoreLabelLayer() {
    if (!state.expandedLeafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.expandedScoreLabelLayer) {
      state.expandedScoreLabelLayer = window.L.layerGroup().addTo(
        state.expandedLeafletMap
      );
    }
    return state.expandedScoreLabelLayer;
  }

  function clearExpandedMapScoreLabels() {
    if (state.expandedScoreLabelLayer) {
      state.expandedScoreLabelLayer.clearLayers();
    }
  }

  function expandedMapRatedGridMarkerLayer() {
    if (!state.expandedLeafletMap || !leafletAvailable()) {
      return null;
    }
    if (!state.expandedRatedGridMarkerLayer) {
      state.expandedRatedGridMarkerLayer = window.L.layerGroup().addTo(
        state.expandedLeafletMap
      );
    }
    return state.expandedRatedGridMarkerLayer;
  }

  function clearExpandedRatedGridMarkers() {
    if (state.expandedRatedGridMarkerLayer) {
      state.expandedRatedGridMarkerLayer.clearLayers();
    }
  }

  function clearExpandedMapGridBoundaries() {
    if (state.expandedGridBoundaryLayer) {
      state.expandedGridBoundaryLayer.clearLayers();
    }
    clearExpandedMapScoreLabels();
    clearExpandedRatedGridMarkers();
    state.expandedMapGridRectanglesById = new Map();
  }

  function resetExpandedMapState() {
    state.expandedLeafletMap = null;
    state.expandedMapAreaRectangle = null;
    state.expandedGridBoundaryLayer = null;
    state.expandedScoreLabelLayer = null;
    state.expandedRatedGridMarkerLayer = null;
    state.expandedMapGridRectanglesById = new Map();
    state.expandedSelectionDrag.suppressNextClick = false;
  }

  function destroyExpandedMap() {
    const expandedLeafletMap = state.expandedLeafletMap;
    cleanupDragSelection(expandedLeafletMap, state.expandedSelectionDrag);
    resetExpandedMapState();

    if (expandedLeafletMap) {
      expandedLeafletMap.remove();
    }
  }

  function drawExpandedMapAreaRectangle(bounds) {
    if (!state.expandedLeafletMap) {
      return;
    }
    if (state.expandedMapAreaRectangle) {
      state.expandedMapAreaRectangle.remove();
    }

    state.expandedMapAreaRectangle = window.L.rectangle(bounds, {
      color: "#176f5c",
      weight: 2,
      fill: false,
      interactive: false,
    }).addTo(state.expandedLeafletMap);
  }

  function fitExpandedMapAreaBounds(bounds) {
    if (!state.expandedLeafletMap) {
      return;
    }
    state.expandedLeafletMap.invalidateSize();
    state.expandedLeafletMap.fitBounds(bounds, {
      padding: [18, 18],
      maxZoom: 19,
    });
    state.expandedLeafletMap.invalidateSize();
    updateExpandedMapScoreLabelSize();
  }

  function refreshExpandedMapLayout(bounds) {
    if (!state.expandedLeafletMap) {
      return;
    }
    fitExpandedMapAreaBounds(bounds);

    window.setTimeout(() => {
      if (!state.expandedLeafletMap || !expandedMapIsOpen()) {
        return;
      }
      fitExpandedMapAreaBounds(bounds);
    }, 80);
  }

  function expandedMapPreviewHasSize() {
    if (!expandedMapPreviewElement) {
      return false;
    }
    return (
      expandedMapPreviewElement.clientWidth > 0 &&
      expandedMapPreviewElement.clientHeight > 0
    );
  }

  function waitForExpandedMapPreviewSize(callback, attempts = 0) {
    if (!expandedMapIsOpen()) {
      return;
    }

    if (expandedMapPreviewHasSize() || attempts >= 8) {
      callback();
      return;
    }

    // モーダル表示直後は地図コンテナが0pxになることがあるため、少し待ってから描く。
    window.setTimeout(() => {
      waitForExpandedMapPreviewSize(callback, attempts + 1);
    }, 50);
  }

  function prepareExpandedBaseMap(bounds) {
    ensureExpandedLeafletMap();

    if (!state.expandedLeafletMap) {
      return;
    }

    const center = boundsCenter(bounds);
    if (center) {
      state.expandedLeafletMap.setView(center, 13, {
        animate: false,
      });
    }
    state.expandedLeafletMap.invalidateSize();
  }

  function createMapScoreLabel(grid, center) {
    // スコア数値はLeaflet markerではなく軽いdivIconとして重ねる。
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

    if (!state.scoreLabelsVisible) {
      return;
    }

    if (!Array.isArray(grids) || grids.length === 0) {
      return;
    }

    const labelLayer = mapScoreLabelLayer();
    if (!labelLayer) {
      return;
    }

    // スコア色の面に数値を足すことで、地図上で点数を確認しやすくする。
    grids.forEach((grid) => {
      const center = gridCellCenter(grid);
      if (!center) {
        return;
      }

      createMapScoreLabel(grid, center).addTo(labelLayer);
    });
    updateMapScoreLabelSize();
  }

  function renderExpandedMapScoreLabels(grids) {
    if (!expandedMapIsOpen()) {
      return;
    }

    clearExpandedMapScoreLabels();

    if (!state.scoreLabelsVisible) {
      return;
    }

    if (!Array.isArray(grids) || grids.length === 0) {
      return;
    }

    const labelLayer = expandedMapScoreLabelLayer();
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
    updateExpandedMapScoreLabelSize();
  }

  function updateScoreLabelVisibility() {
    if (scoreLabelToggleInput) {
      state.scoreLabelsVisible = scoreLabelToggleInput.checked;
    }
    const grids = Array.from(state.gridsById.values());
    renderMapScoreLabels(grids);
    if (expandedMapIsOpen()) {
      renderExpandedMapScoreLabels(grids);
    }
  }

  function ratedGridMarkerPosition(grid) {
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
      north - (north - south) * 0.12,
      east - (east - west) * 0.12,
    ];
  }

  function createRatedGridMarker(position) {
    return window.L.marker(position, {
      interactive: false,
      keyboard: false,
      icon: window.L.divIcon({
        className: "map-rated-grid-marker",
        html: "<span>✓</span>",
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      }),
    });
  }

  function renderRatedGridMarkers(grids) {
    clearRatedGridMarkers();

    if (!state.ratedGridMarkersVisible) {
      return;
    }

    if (!Array.isArray(grids) || grids.length === 0) {
      return;
    }

    const markerLayer = mapRatedGridMarkerLayer();
    if (!markerLayer) {
      return;
    }

    // 自分が採点済みのマスだけを軽い印で示し、未採点マスを探しやすくする。
    grids.forEach((grid) => {
      if (!grid.current_user_has_rating) {
        return;
      }

      const position = ratedGridMarkerPosition(grid);
      if (!position) {
        return;
      }

      createRatedGridMarker(position).addTo(markerLayer);
    });
  }

  function renderExpandedRatedGridMarkers(grids) {
    if (!expandedMapIsOpen()) {
      return;
    }

    clearExpandedRatedGridMarkers();

    if (!state.ratedGridMarkersVisible) {
      return;
    }

    if (!Array.isArray(grids) || grids.length === 0) {
      return;
    }

    const markerLayer = expandedMapRatedGridMarkerLayer();
    if (!markerLayer) {
      return;
    }

    grids.forEach((grid) => {
      if (!grid.current_user_has_rating) {
        return;
      }

      const position = ratedGridMarkerPosition(grid);
      if (!position) {
        return;
      }

      createRatedGridMarker(position).addTo(markerLayer);
    });
  }

  function updateRatedGridMarkerVisibility() {
    if (ratedGridToggleInput) {
      state.ratedGridMarkersVisible = ratedGridToggleInput.checked;
    }
    const grids = Array.from(state.gridsById.values());
    renderRatedGridMarkers(grids);
    if (expandedMapIsOpen()) {
      renderExpandedRatedGridMarkers(grids);
    }
  }

  function gridIdForMap(grid) {
    const gridId = Number(grid.id);
    return Number.isFinite(gridId) ? gridId : null;
  }

  function dragStateForMapEvent(event) {
    if (event.target === state.expandedLeafletMap) {
      return state.expandedSelectionDrag;
    }
    return state.normalSelectionDrag;
  }

  function handleMapGridClick(gridId, event) {
    const originalEvent = event.originalEvent;
    const dragState = dragStateForMapEvent(event);
    if (
      dragState.suppressNextClick ||
      (originalEvent && originalEvent.shiftKey)
    ) {
      return;
    }
    if (originalEvent && (originalEvent.ctrlKey || originalEvent.metaKey)) {
      toggleGridSelection(gridId);
      return;
    }

    // 通常クリックは単体採点を素早く始めるため、選択集合を1件に絞る。
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

  function createExpandedMapGridRectangle(grid, gridId, bounds) {
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

  function renderExpandedMapGridBoundary(grid, boundaryLayer) {
    const bounds = gridCellBounds(grid);
    if (!bounds) {
      return;
    }

    const gridId = gridIdForMap(grid);
    if (gridId === null) {
      return;
    }

    const rectangle = createExpandedMapGridRectangle(grid, gridId, bounds).addTo(
      boundaryLayer
    );
    state.expandedMapGridRectanglesById.set(gridId, rectangle);
  }

  function renderExpandedMapGridBoundaries(grids) {
    if (!expandedMapIsOpen()) {
      return;
    }

    clearExpandedMapGridBoundaries();

    if (!state.expandedLeafletMap) {
      return;
    }

    if (!Array.isArray(grids) || grids.length === 0) {
      bringExpandedMapAreaRectangleToFront();
      return;
    }

    const boundaryLayer = expandedMapGridBoundaryLayer();
    if (!boundaryLayer) {
      return;
    }

    grids.forEach((grid) => {
      renderExpandedMapGridBoundary(grid, boundaryLayer);
    });

    updateSelectedMapGridState();
    renderExpandedMapScoreLabels(grids);
    renderExpandedRatedGridMarkers(grids);
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

    // 同じGridCellデータから面の色、スコアラベル、採点済み表示をまとめて描く。
    grids.forEach((grid) => {
      renderMapGridBoundary(grid, boundaryLayer);
    });

    updateSelectedMapGridState();
    renderMapScoreLabels(grids);
    renderRatedGridMarkers(grids);
    if (expandedMapIsOpen()) {
      renderExpandedMapGridBoundaries(grids);
    }
  }

  function normalMapReady() {
    return Boolean(state.leafletMap);
  }

  function zoomNormalMapOut() {
    if (!normalMapReady()) {
      return;
    }

    state.leafletMap.zoomOut();
  }

  function zoomNormalMapIn() {
    if (!normalMapReady()) {
      return;
    }

    state.leafletMap.zoomIn();
  }

  function fitNormalMapToArea() {
    if (!normalMapReady()) {
      return;
    }

    const bounds = readMapAreaBounds();
    if (!bounds) {
      return;
    }

    fitMapAreaBounds(bounds);
    updateMapScoreLabelSize();
  }

  function expandedMapIsOpen() {
    return expandedMapModalElement && !expandedMapModalElement.hidden;
  }

  function expandedMapReady() {
    return expandedMapIsOpen() && state.expandedLeafletMap;
  }

  function zoomExpandedMapOut() {
    if (!expandedMapReady()) {
      return;
    }

    state.expandedLeafletMap.zoomOut();
  }

  function zoomExpandedMapIn() {
    if (!expandedMapReady()) {
      return;
    }

    state.expandedLeafletMap.zoomIn();
  }

  function fitExpandedMapToArea() {
    if (!expandedMapReady()) {
      return;
    }

    const bounds = readMapAreaBounds();
    if (!bounds) {
      return;
    }

    refreshExpandedMapLayout(bounds);
  }

  function openExpandedMapPreview() {
    if (!expandedMapModalElement || !expandedMapPreviewElement) {
      return;
    }

    if (!leafletAvailable()) {
      setMapPreviewStatus("地図ライブラリを読み込めませんでした。", "error");
      return;
    }

    const bounds = readMapAreaBounds();
    if (!bounds) {
      setMapPreviewStatus("メモグリッド範囲を拡大表示できません。", "error");
      return;
    }

    expandedMapModalElement.hidden = false;
    document.body.classList.add("is-expanded-map-open");

    window.requestAnimationFrame(() => {
      if (!expandedMapIsOpen()) {
        return;
      }

      waitForExpandedMapPreviewSize(() => {
        prepareExpandedBaseMap(bounds);

        window.setTimeout(() => {
          if (!expandedMapIsOpen() || !state.expandedLeafletMap) {
            return;
          }

          drawExpandedMapAreaRectangle(bounds);
          renderExpandedMapGridBoundaries(Array.from(state.gridsById.values()));
          refreshExpandedMapLayout(bounds);
        }, 80);
      });

      if (closeExpandedMapButton) {
        closeExpandedMapButton.focus();
      }
    });
  }

  function closeExpandedMapPreview() {
    if (!expandedMapModalElement || expandedMapModalElement.hidden) {
      return;
    }

    expandedMapModalElement.hidden = true;
    document.body.classList.remove("is-expanded-map-open");
    destroyExpandedMap();

    if (state.leafletMap) {
      window.setTimeout(() => {
        state.leafletMap.invalidateSize();
        updateMapScoreLabelSize();
      }, 0);
    }

    if (expandMapPreviewButton) {
      expandMapPreviewButton.focus();
    }
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

    // 共有管理は作成者用の操作なので、表示されている画面だけで一覧を同期する。
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

    // 追加後に一覧を取り直し、権限状態を画面内で完結して確認できるようにする。
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

    // 共有解除は相手の閲覧・採点権限に影響するため、確認を挟んでから実行する。
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

    // MapArea削除は関連するGridCell・採点・共有設定も消えるため、完了後は一覧へ戻す。
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
      // 採点後や再取得時はAPIから取り直し、表示スコアとコメントを最新状態にする。
      const data = await api.fetchGridCells(areaId);
      renderGrids(data && data.grids ? data.grids : [], options);
    } catch (error) {
      renderGridListLoadError(error);
    } finally {
      setReloadGridCellsButtonDisabled(false);
    }
  }

  function reloadGridCells() {
    // 手動再取得では現在の選択を保ち、地図だけ最新のGridCell情報へ差し替える。
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
      // 採点APIの戻り値だけに頼らず、再取得して地図色・数値・コメントを揃える。
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
      // 単体採点後も再取得し、計算済みスコアと選択欄を同じデータで更新する。
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

    if (expandMapPreviewButton) {
      expandMapPreviewButton.addEventListener("click", () => {
        openExpandedMapPreview();
      });
    }

    if (mapPreviewZoomOutButton) {
      mapPreviewZoomOutButton.addEventListener("click", () => {
        zoomNormalMapOut();
      });
    }

    if (mapPreviewZoomInButton) {
      mapPreviewZoomInButton.addEventListener("click", () => {
        zoomNormalMapIn();
      });
    }

    if (mapPreviewFitBoundsButton) {
      mapPreviewFitBoundsButton.addEventListener("click", () => {
        fitNormalMapToArea();
      });
    }

    if (closeExpandedMapButton) {
      closeExpandedMapButton.addEventListener("click", () => {
        closeExpandedMapPreview();
      });
    }

    if (expandedMapModalElement) {
      expandedMapModalElement.addEventListener("click", (event) => {
        if (event.target.closest("[data-expanded-map-close]")) {
          closeExpandedMapPreview();
        }
      });

      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || !expandedMapIsOpen()) {
          return;
        }

        event.preventDefault();
        closeExpandedMapPreview();
      });
    }

    if (expandedMapZoomOutButton) {
      expandedMapZoomOutButton.addEventListener("click", () => {
        zoomExpandedMapOut();
      });
    }

    if (expandedMapZoomInButton) {
      expandedMapZoomInButton.addEventListener("click", () => {
        zoomExpandedMapIn();
      });
    }

    if (expandedMapFitBoundsButton) {
      expandedMapFitBoundsButton.addEventListener("click", () => {
        fitExpandedMapToArea();
      });
    }

    if (gridOpacityScaleInput) {
      state.gridOpacityScaleValue = readGridOpacityScaleValue();
      updateGridOpacityScaleValueText();
      gridOpacityScaleInput.addEventListener("input", updateGridOpacityScale);
      gridOpacityScaleInput.addEventListener("change", updateGridOpacityScale);
    }

    if (scoreLabelToggleInput) {
      state.scoreLabelsVisible = scoreLabelToggleInput.checked;
      scoreLabelToggleInput.addEventListener("change", updateScoreLabelVisibility);
    }

    if (ratedGridToggleInput) {
      state.ratedGridMarkersVisible = ratedGridToggleInput.checked;
      ratedGridToggleInput.addEventListener("change", updateRatedGridMarkerVisibility);
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
