(function () {
  const formElement = document.querySelector("#map-area-create-form");
  const statusElement = document.querySelector("#memo-grid-create-status");
  const submitButton = document.querySelector("#map-area-create-submit");

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
      source: fieldValue("source"),
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
      return Object.entries(data)
        .map(([key, value]) => {
          const detail = Array.isArray(value) ? value.join(" ") : String(value);
          return `${key}: ${detail}`;
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

    if (submitButton) {
      submitButton.disabled = true;
    }
    setStatus("メモグリッドを作成しています。");

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
            ? `HTTP ${response.status}. ${detail}`
            : `HTTP ${response.status}.`
        );
      }

      if (!data || !data.id) {
        throw new Error("作成されたメモグリッドIDを取得できませんでした。");
      }

      setStatus("メモグリッドを作成しました。詳細画面へ移動します。", "success");
      window.location.href = `/maps/${data.id}/`;
    } catch (error) {
      setStatus(`メモグリッドを作成できませんでした。${error.message}`, "error");
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  }

  if (formElement) {
    formElement.addEventListener("submit", (event) => {
      event.preventDefault();
      submitMapArea();
    });
  }
})();
