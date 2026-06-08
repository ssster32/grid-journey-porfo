(function () {
  const rootElement = document.querySelector("#grid-detail-root");
  const messageElement = document.querySelector("#grid-cell-list-message");
  const countElement = document.querySelector("#grid-cell-count");
  const listElement = document.querySelector("#grid-cell-list");
  const selectedGridDetailElement = document.querySelector(
    "#selected-grid-cell-detail"
  );
  const ratingFormContainer = document.querySelector("#grid-rating-form-container");
  const maxVisibleGridCount = 50;
  const state = {
    gridsById: new Map(),
    selectedGridId: null,
  };

  function setMessage(text, type = "") {
    if (!messageElement) {
      return;
    }
    messageElement.textContent = text;
    messageElement.dataset.messageType = type;
  }

  function setCount(text) {
    if (!countElement) {
      return;
    }
    countElement.textContent = text;
  }

  function clearList() {
    if (!listElement) {
      return;
    }
    listElement.replaceChildren();
  }

  function textOrFallback(value, fallback = "未設定") {
    if (value === null || value === undefined || value === "") {
      return fallback;
    }
    return String(value);
  }

  function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
      return "未設定";
    }

    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
      return String(value);
    }

    return Number.isInteger(numberValue)
      ? String(numberValue)
      : numberValue.toFixed(1);
  }

  function formatCoordinate(value) {
    if (value === null || value === undefined || value === "") {
      return "未設定";
    }

    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
      return String(value);
    }

    return numberValue.toFixed(6);
  }

  function formatDateTime(value) {
    if (!value) {
      return "未更新";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function displayIndex(value) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
      return "未設定";
    }
    return String(numberValue + 1);
  }

  function createGridItem(grid) {
    const item = document.createElement("li");
    const gridId = Number(grid.id);
    item.className = "grid-cell-item";
    item.dataset.gridId = textOrFallback(grid.id, "");
    item.classList.toggle("is-selected", state.selectedGridId === gridId);

    const summary = document.createElement("span");
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
    selectButton.dataset.selectGridId = textOrFallback(grid.id, "");
    selectButton.textContent = state.selectedGridId === gridId ? "選択中" : "選択";

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

  function createDetailItem(label, value) {
    const item = document.createElement("li");
    item.textContent = `${label}: ${value}`;
    return item;
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

    selectedGridDetailElement.append(heading, position, detailList);
  }

  function renderRatingForm(grid) {
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
    target.textContent = `対象: マス #${textOrFallback(grid.id)}`;

    const form = document.createElement("form");

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
    submitButton.disabled = true;
    submitButton.textContent = "採点する";

    const note = document.createElement("p");
    note.textContent = "採点送信は次回以降に実装します。";

    form.append(scoreLabel, commentLabel, submitButton, note);
    ratingFormContainer.append(target, form);
  }

  function updateSelectedGridListState() {
    if (!listElement) {
      return;
    }

    listElement.querySelectorAll(".grid-cell-item").forEach((item) => {
      const itemGridId = Number(item.dataset.gridId);
      const isSelected = state.selectedGridId === itemGridId;
      item.classList.toggle("is-selected", isSelected);

      const selectButton = item.querySelector("[data-select-grid-id]");
      if (selectButton) {
        selectButton.textContent = isSelected ? "選択中" : "選択";
      }
    });
  }

  function selectGrid(gridId) {
    const numericGridId = Number(gridId);
    const grid = state.gridsById.get(numericGridId);
    if (!grid) {
      return;
    }

    state.selectedGridId = numericGridId;
    renderSelectedGridDetail(grid);
    renderRatingForm(grid);
    updateSelectedGridListState();
  }

  function renderGrids(grids) {
    clearList();
    state.gridsById = new Map();
    state.selectedGridId = null;

    if (!Array.isArray(grids) || grids.length === 0) {
      setCount("");
      setMessage("このメモグリッドには、まだマスがありません。");
      setSelectedGridDetail("表示できるマスがありません。");
      setRatingFormMessage("表示できるマスがないため、採点フォームは表示できません。");
      return;
    }

    state.gridsById = new Map(
      grids.map((grid) => [Number(grid.id), grid])
    );
    setCount(`マス数: ${grids.length}`);
    setMessage("マス一覧を取得しました。");
    renderSelectedGridDetail(null);
    renderRatingForm(null);

    const visibleGrids = grids.slice(0, maxVisibleGridCount);
    const list = document.createElement("ul");
    visibleGrids.forEach((grid) => {
      list.appendChild(createGridItem(grid));
    });
    listElement.appendChild(list);

    if (grids.length > maxVisibleGridCount) {
      const limitNote = document.createElement("p");
      limitNote.textContent = `先頭${maxVisibleGridCount}件を表示しています。`;
      listElement.appendChild(limitNote);
    }
  }

  async function readResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return null;
    }
    return response.json();
  }

  async function loadGridCells() {
    const areaId = rootElement ? rootElement.dataset.areaId : "";
    if (!areaId) {
      setMessage("マス一覧を取得できませんでした。area_id が見つかりません。", "error");
      return;
    }

    setMessage("マス一覧を読み込んでいます。");
    setCount("");
    clearList();

    try {
      const response = await fetch(`/api/maps/areas/${areaId}/grids/`, {
        credentials: "same-origin",
      });
      const data = await readResponse(response);

      if (!response.ok) {
        const detail = data && data.detail ? ` ${data.detail}` : "";
        throw new Error(`HTTP ${response.status}.${detail}`);
      }

      renderGrids(data && data.grids ? data.grids : []);
    } catch (error) {
      setCount("");
      clearList();
      setMessage(`マス一覧を取得できませんでした。${error.message}`, "error");
      setSelectedGridDetail("マス一覧を取得できなかったため、マスを選択できません。");
      setRatingFormMessage(
        "マス一覧を取得できなかったため、採点フォームは表示できません。"
      );
    }
  }

  if (rootElement && messageElement && countElement && listElement) {
    listElement.addEventListener("click", (event) => {
      const selectButton = event.target.closest("[data-select-grid-id]");
      if (!selectButton) {
        return;
      }

      selectGrid(selectButton.dataset.selectGridId);
    });

    loadGridCells();
  }
})();
