(function () {
  const messageElement = document.querySelector("#map-area-list-message");
  const helperElement = document.querySelector("#map-area-list-helper");
  const listElement = document.querySelector("#map-area-list");

  function setMessage(text, type = "") {
    if (!messageElement) {
      return;
    }
    messageElement.textContent = text;
    messageElement.dataset.messageType = type;
  }

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

  function clearList() {
    if (!listElement) {
      return;
    }
    listElement.replaceChildren();
  }

  function clearHelper() {
    if (!helperElement) {
      return;
    }
    helperElement.replaceChildren();
  }

  function createHelperCard(title, body) {
    const section = document.createElement("section");
    section.className = "content-section map-area-list-helper-card";

    const heading = document.createElement("h2");
    heading.textContent = title;

    const description = document.createElement("p");
    description.textContent = body;

    const actions = document.createElement("div");
    actions.className = "section-actions";

    section.append(heading, description, actions);

    return { section, actions };
  }

  function renderEmptyState() {
    clearHelper();
    if (!helperElement) {
      return;
    }

    const { section, actions } = createHelperCard(
      "メモグリッドはまだありません",
      "最初のメモグリッドを作成すると、ここに一覧として表示されます。"
    );
    const createLink = document.createElement("a");
    createLink.className = "detail-link";
    createLink.href = "/maps/new/";
    createLink.textContent = "新しいメモグリッドを作成";
    actions.appendChild(createLink);
    helperElement.appendChild(section);
  }

  function renderLoadErrorState() {
    clearHelper();
    if (!helperElement) {
      return;
    }

    const { section, actions } = createHelperCard(
      "一覧を取得できませんでした",
      "通信状況やログイン状態を確認して、もう一度読み込みを試してください。"
    );
    const reloadButton = document.createElement("button");
    reloadButton.type = "button";
    reloadButton.className = "secondary-button";
    reloadButton.dataset.reloadMapAreas = "";
    reloadButton.textContent = "再読み込み";
    actions.appendChild(reloadButton);
    helperElement.appendChild(section);
  }

  function textOrFallback(value, fallback = "未設定") {
    if (value === null || value === undefined || value === "") {
      return fallback;
    }
    return String(value);
  }

  function formatDate(value) {
    if (!value) {
      return "未設定";
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

  function ownerLabel(area) {
    if (area.is_owner) {
      return "自分";
    }
    return textOrFallback(area.created_by_username, "不明");
  }

  function initialScoreModeLabel(value) {
    if (value === "auto") {
      return "自動設定";
    }
    if (value === "manual") {
      return "手動設定";
    }
    return textOrFallback(value);
  }

  function regionFeatureLevelLabel(area) {
    if (area && area.initial_score_mode === "auto") {
      return "-";
    }

    const value = area ? area.region_feature_level : undefined;
    if (value === null || value === undefined || value === "") {
      return "未設定";
    }
    if (Number(value) === 0) {
      return "0: 初期値";
    }
    if (Number(value) === 1) {
      return "1: ありふれた地域";
    }
    if (Number(value) === 2) {
      return "2: 普通の地域";
    }
    if (Number(value) === 3) {
      return "3: 特徴的な地域";
    }
    return String(value);
  }

  function gridCountLabel(area) {
    if (!area || !area.map_grid_rows || !area.map_grid_cols) {
      return "未設定";
    }
    return `縦 ${area.map_grid_rows} × 横 ${area.map_grid_cols}`;
  }

  function gridGenerationStatusLabel(area) {
    const statusValue = area ? area.grid_generation_status : "";
    if (statusValue === "fallback_completed") {
      return "標準値で作成";
    }
    return textOrFallback(
      area && area.grid_generation_status_display,
      "作成状態不明"
    );
  }

  function gridGenerationStatusNote(area) {
    const statusValue = area ? area.grid_generation_status : "";
    if (statusValue === "pending") {
      return "自動設定の処理待ちです。";
    }
    if (statusValue === "running") {
      return "地図データを取得中です。";
    }
    if (statusValue === "fallback_completed") {
      return "自動設定に失敗したため標準値で作成しました。";
    }
    if (statusValue === "failed") {
      return "メモグリッドの作成に失敗しました。";
    }
    return "";
  }

  function createGridGenerationStatus(area) {
    const wrapper = document.createElement("div");
    const statusValue = textOrFallback(
      area && area.grid_generation_status,
      "unknown"
    );
    wrapper.className = "map-area-generation-status";

    const badge = document.createElement("span");
    badge.className = `status-badge status-badge--${statusValue}`;
    badge.textContent = gridGenerationStatusLabel(area);
    wrapper.appendChild(badge);

    const noteText = gridGenerationStatusNote(area);
    if (noteText) {
      const note = document.createElement("p");
      note.className = "status-note";
      note.textContent = noteText;
      wrapper.appendChild(note);
    }

    return wrapper;
  }

  function createMetaItem(label, value) {
    const item = document.createElement("li");
    const labelElement = document.createElement("span");
    const valueElement = document.createElement("span");

    labelElement.textContent = `${label}: `;
    valueElement.textContent = value;

    item.append(labelElement, valueElement);
    return item;
  }

  function createAreaCard(area) {
    const article = document.createElement("article");
    article.className = "map-area-list-item";
    if (!area.is_owner) {
      article.classList.add("shared-map-area-card");
    }
    article.dataset.areaId = textOrFallback(area.id, "");

    const heading = document.createElement("h2");
    heading.textContent = textOrFallback(area.name, "名前未設定");

    const description = document.createElement("p");
    description.className = "map-area-description";
    description.textContent = textOrFallback(area.description, "説明はありません。");

    const displayType = textOrFallback(area.display_type, "メモグリッド");
    const badge = document.createElement("p");
    badge.className = "map-area-badge";
    badge.textContent = area.is_owner
      ? `自分の${displayType}`
      : displayType;
    const gridGenerationStatus = createGridGenerationStatus(area);

    const metaList = document.createElement("ul");
    metaList.className = "map-area-meta-list";
    metaList.append(
      createMetaItem("作成者", ownerLabel(area)),
      createMetaItem("初期スコア設定", initialScoreModeLabel(area.initial_score_mode)),
      createMetaItem("地域特徴レベル", regionFeatureLevelLabel(area)),
      createMetaItem("1マスの大きさ", `${textOrFallback(area.grid_size_meters)}m`),
      createMetaItem("マスの数", gridCountLabel(area)),
      createMetaItem("作成日時", formatDate(area.created_at))
    );

    const actionWrapper = document.createElement("div");
    actionWrapper.className = "map-area-actions";
    if (area.id) {
      const detailLink = document.createElement("a");
      detailLink.className = "detail-link";
      detailLink.href = `/maps/${area.id}/`;
      detailLink.textContent = "詳細を見る";
      actionWrapper.appendChild(detailLink);
    } else {
      actionWrapper.textContent = "詳細画面へのリンクを作成できません。";
    }

    let dangerArea = null;
    if (area.id && area.is_owner) {
      dangerArea = document.createElement("div");
      dangerArea.className = "map-area-danger-actions";

      const dangerNote = document.createElement("p");
      dangerNote.className = "map-area-danger-note";
      dangerNote.textContent = "削除すると元に戻せません。";

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "danger-button";
      deleteButton.dataset.deleteAreaId = textOrFallback(area.id, "");
      deleteButton.dataset.areaName = textOrFallback(area.name, "名前未設定");
      deleteButton.textContent = "削除";

      dangerArea.append(dangerNote, deleteButton);
    }

    article.append(
      heading,
      badge,
      gridGenerationStatus,
      description,
      metaList,
      actionWrapper
    );
    if (dangerArea) {
      article.appendChild(dangerArea);
    }
    return article;
  }

  function renderAreas(areas) {
    clearList();
    clearHelper();

    if (!Array.isArray(areas) || areas.length === 0) {
      setMessage("メモグリッドはまだありません。");
      renderEmptyState();
      return;
    }

    setMessage("");
    const fragment = document.createDocumentFragment();
    areas.forEach((area) => {
      fragment.appendChild(createAreaCard(area));
    });
    listElement.appendChild(fragment);
  }

  async function readResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return null;
    }
    return response.json();
  }

  function errorText(response, data) {
    if (!data) {
      return `通信エラー ${response.status}.`;
    }
    if (data.detail) {
      return `通信エラー ${response.status}. ${data.detail}`;
    }
    return `通信エラー ${response.status}. ${JSON.stringify(data)}`;
  }

  async function loadMapAreas() {
    setMessage("メモグリッド一覧を読み込んでいます。");
    clearList();
    clearHelper();

    try {
      const response = await fetch("/api/maps/areas/", {
        credentials: "same-origin",
      });
      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(errorText(response, data));
      }

      renderAreas(data && data.areas ? data.areas : []);
    } catch (error) {
      clearList();
      setMessage(
        `メモグリッド一覧を取得できませんでした。${error.message}`,
        "error"
      );
      renderLoadErrorState();
    }
  }

  async function deleteMapArea(deleteButton) {
    const areaId = deleteButton.dataset.deleteAreaId;
    const areaName = deleteButton.dataset.areaName || "このメモグリッド";
    if (!areaId) {
      setMessage("削除対象のメモグリッドIDが見つかりません。", "error");
      return;
    }

    const confirmed = window.confirm(
      `メモグリッド「${areaName}」を削除します。関連するマス、採点、共有設定も削除されます。よろしいですか？`
    );
    if (!confirmed) {
      return;
    }

    deleteButton.disabled = true;
    setMessage("メモグリッドを削除しています。");

    try {
      const response = await fetch(`/api/maps/areas/${areaId}/`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });
      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(errorText(response, data));
      }

      await loadMapAreas();
      setMessage("メモグリッドを削除しました。", "success");
    } catch (error) {
      deleteButton.disabled = false;
      setMessage(`メモグリッドを削除できませんでした。${error.message}`, "error");
    }
  }

  if (messageElement && listElement) {
    if (helperElement) {
      helperElement.addEventListener("click", (event) => {
        const reloadButton = event.target.closest("[data-reload-map-areas]");
        if (!reloadButton) {
          return;
        }

        loadMapAreas();
      });
    }

    listElement.addEventListener("click", (event) => {
      const deleteButton = event.target.closest("[data-delete-area-id]");
      if (!deleteButton) {
        return;
      }

      deleteMapArea(deleteButton);
    });

    loadMapAreas();
  }
})();
