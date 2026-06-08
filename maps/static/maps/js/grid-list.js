(function () {
  const messageElement = document.querySelector("#map-area-list-message");
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

    const metaList = document.createElement("ul");
    metaList.className = "map-area-meta-list";
    metaList.append(
      createMetaItem("作成者", ownerLabel(area)),
      createMetaItem("初期スコア設定", textOrFallback(area.initial_score_mode)),
      createMetaItem("地域特徴レベル", textOrFallback(area.region_feature_level)),
      createMetaItem("1マスの大きさ", `${textOrFallback(area.grid_size_meters)}m`),
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

    if (area.id && area.is_owner) {
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "danger-button";
      deleteButton.dataset.deleteAreaId = textOrFallback(area.id, "");
      deleteButton.dataset.areaName = textOrFallback(area.name, "名前未設定");
      deleteButton.textContent = "削除";
      actionWrapper.appendChild(deleteButton);
    }

    article.append(heading, badge, description, metaList, actionWrapper);
    return article;
  }

  function renderAreas(areas) {
    clearList();

    if (!Array.isArray(areas) || areas.length === 0) {
      setMessage("メモグリッドはまだありません。");
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
      return `HTTP ${response.status}.`;
    }
    if (data.detail) {
      return `HTTP ${response.status}. ${data.detail}`;
    }
    return `HTTP ${response.status}. ${JSON.stringify(data)}`;
  }

  async function loadMapAreas() {
    setMessage("メモグリッド一覧を読み込んでいます。");
    clearList();

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
