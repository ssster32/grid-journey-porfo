(() => {
  "use strict";

  const autoScoreBreakdownLabels = {
    base_score: "基礎スコア",
    building_base_bonus: "建物による基礎加点",
    road_base_bonus: "道路による基礎加点",
    diversity_bonus: "要素の多様性",
    context_bonus: "周辺要素の加点",
    penalty: "減点",
    raw_score: "補正前スコア",
    clamped_score: "自動初期スコア",
    bonuses: "加点内訳",
    flags: "判定項目",
    has_building: "建物",
    has_road: "道路",
    has_park: "公園・緑地",
    has_river: "川・水路",
    has_water: "水辺",
    has_scored_forest: "森林",
    has_park_context: "公園周辺",
    has_river_context: "川周辺",
    has_forest_context: "森林周辺",
    has_coastal_context: "海岸周辺",
    has_waterfront_context: "水辺周辺",
    has_surface_railway_context: "地上線路",
    has_surface_station_context: "地上駅",
    has_subway_station_context: "地下鉄駅",
    has_public_transport_station_context: "公共交通駅",
    has_dense_station_cluster_context: "駅密集",
    has_major_station_cluster_context: "主要駅クラスター",
    has_station_proximity_context: "駅近接",
    has_station_proximity_near_context: "駅近接（近距離）",
    has_station_proximity_mid_context: "駅近接（中距離）",
    has_motorway_context: "高速道路",
    has_trunk_context: "幹線道路",
    has_landmark_context: "観光名所",
    landmark_context_bonus: "観光名所による加点",
    has_castle_proximity_context: "城周辺",
    has_castle_near_proximity_context: "城周辺（近距離）",
    has_castle_mid_proximity_context: "城周辺（中距離）",
    has_castle_far_proximity_context: "城周辺（遠距離）",
    castle_proximity_bonus: "城周辺による加点",
    has_park_waterfront_combo_context: "公園 + 水辺",
    park_waterfront_combo_bonus: "公園 + 水辺による加点",
    has_high_context_3_context: "特徴要素が多い地域",
    has_high_context_4_context: "特徴要素がかなり多い地域",
    has_high_context_5_context: "特徴要素が非常に多い地域",
    high_context_bonus: "特徴要素数による加点",
    has_water_penalty: "水域中心のため減点",
    has_unreachable_water_penalty: "到達しにくい水域のため減点",
    has_forest_penalty: "森林中心のため減点",
    has_empty_cell_penalty: "建物・道路なしのため減点",
  };

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

  function autoScoreLabel(key) {
    if (autoScoreBreakdownLabels[key]) {
      return autoScoreBreakdownLabels[key];
    }
    return String(key)
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function isPlainObject(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value)
    );
  }

  function hasAutoScoreBreakdown(value) {
    return isPlainObject(value) && Object.keys(value).length > 0;
  }

  function formatAutoScoreNumber(value) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
      return "未記録";
    }
    return Number.isInteger(numberValue)
      ? String(numberValue)
      : numberValue.toFixed(1);
  }

  function formatAutoScoreValue(value) {
    if (value === null || value === undefined || value === "") {
      return "未記録";
    }
    if (typeof value === "boolean") {
      return value ? "あり" : "なし";
    }
    if (typeof value === "number") {
      return formatAutoScoreNumber(value);
    }
    if (Array.isArray(value)) {
      return value.length ? value.map(formatAutoScoreValue).join(", ") : "未記録";
    }
    if (isPlainObject(value)) {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return "未記録";
      }
      return entries
        .map(([key, childValue]) => `${autoScoreLabel(key)}: ${formatAutoScoreValue(childValue)}`)
        .join(" / ");
    }
    return String(value);
  }

  function autoScoreReasonLabels(breakdown) {
    const flags = isPlainObject(breakdown.flags) ? breakdown.flags : {};
    const bonuses = isPlainObject(breakdown.bonuses) ? breakdown.bonuses : {};
    const reasonRules = [
      ["has_landmark_context", "観光名所"],
      ["has_castle_proximity_context", "城周辺"],
      ["has_park_waterfront_combo_context", "公園 + 水辺"],
      ["has_high_context_5_context", "特徴要素が非常に多い地域"],
      ["has_high_context_4_context", "特徴要素がかなり多い地域"],
      ["has_high_context_3_context", "特徴要素が多い地域"],
      ["has_station_proximity_context", "駅近接"],
      ["has_dense_station_cluster_context", "駅密集"],
      ["has_major_station_cluster_context", "主要駅クラスター"],
      ["has_surface_station_context", "地上駅"],
      ["has_subway_station_context", "地下鉄駅"],
      ["has_public_transport_station_context", "公共交通駅"],
      ["has_surface_railway_context", "地上線路"],
      ["has_motorway_context", "高速道路"],
      ["has_trunk_context", "幹線道路"],
      ["has_waterfront_context", "水辺周辺"],
      ["has_park_context", "公園"],
      ["has_river_context", "川・水路"],
      ["has_forest_context", "森林"],
      ["has_coastal_context", "海岸"],
    ];
    const penaltyRules = [
      ["has_water_penalty", "水域中心のため減点"],
      ["has_forest_penalty", "森林中心のため減点"],
      ["has_empty_cell_penalty", "建物・道路なしのため減点"],
    ];
    const labels = [];

    reasonRules.forEach(([key, label]) => {
      if (flags[key] && !labels.includes(label)) {
        labels.push(label);
      }
    });
    penaltyRules.forEach(([key, label]) => {
      if (flags[key] && !labels.includes(label)) {
        labels.push(label);
      }
    });
    if (Number(bonuses.landmark_context_bonus) > 0 && !labels.includes("観光名所")) {
      labels.push("観光名所");
    }

    return labels;
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

  function formatScoreLabel(value) {
    if (value === null || value === undefined || value === "") {
      return "-";
    }

    const score = Number(value);
    if (!Number.isFinite(score)) {
      return "-";
    }

    return Number.isInteger(score) ? String(score) : score.toFixed(1);
  }

  window.GridDetailUtils = {
    textOrFallback,
    formatNumber,
    formatCoordinate,
    formatDateTime,
    displayIndex,
    getCookie,
    autoScoreLabel,
    hasAutoScoreBreakdown,
    formatAutoScoreValue,
    autoScoreReasonLabels,
    readResponse,
    errorText,
    formatScoreLabel,
  };
})();
