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

    const heading = document.createElement("h2");
    heading.textContent = textOrFallback(area.name, "名前未設定");

    const description = document.createElement("p");
    description.textContent = textOrFallback(area.description, "説明はありません。");

    const displayType = textOrFallback(area.display_type, "メモグリッド");
    const badge = document.createElement("p");
    badge.textContent = area.is_owner
      ? `自分の${displayType}`
      : displayType;

    const metaList = document.createElement("ul");
    metaList.append(
      createMetaItem("作成者", ownerLabel(area)),
      createMetaItem("初期スコア設定", textOrFallback(area.initial_score_mode)),
      createMetaItem("地域特徴レベル", textOrFallback(area.region_feature_level)),
      createMetaItem("1マスの大きさ", `${textOrFallback(area.grid_size_meters)}m`),
      createMetaItem("作成日時", formatDate(area.created_at))
    );

    const detailWrapper = document.createElement("p");
    if (area.id) {
      const detailLink = document.createElement("a");
      detailLink.href = `/maps/${area.id}/`;
      detailLink.textContent = "詳細を見る";
      detailWrapper.appendChild(detailLink);
    } else {
      detailWrapper.textContent = "詳細画面へのリンクを作成できません。";
    }

    article.append(heading, badge, description, metaList, detailWrapper);
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

  async function loadMapAreas() {
    setMessage("メモグリッド一覧を読み込んでいます。");
    clearList();

    try {
      const response = await fetch("/api/maps/areas/", {
        credentials: "same-origin",
      });
      const data = await readResponse(response);

      if (!response.ok) {
        const detail = data && data.detail ? ` ${data.detail}` : "";
        throw new Error(`HTTP ${response.status}.${detail}`);
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

  if (messageElement && listElement) {
    loadMapAreas();
  }
})();
