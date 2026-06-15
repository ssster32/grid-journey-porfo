(() => {
  "use strict";

  // 詳細画面のAPI通信を集約し、grid-detail.js側を画面制御に集中させる。
  const utils = window.GridDetailUtils;
  if (!utils) {
    console.error("GridDetailUtils is not loaded.");
    return;
  }

  const { getCookie, readResponse, errorText } = utils;

  async function requestJson(url, options = {}) {
    // fetch後のJSON読み取りとエラー文生成を共通化し、各API関数を薄く保つ。
    const response = await fetch(url, options);
    const data = await readResponse(response);

    if (!response.ok) {
      throw new Error(errorText(response, data));
    }

    return data;
  }

  function csrfHeaders(extraHeaders = {}) {
    // POST/DELETEではDjangoのCSRFチェックを通すため、cookieのtokenを付ける。
    return {
      ...extraHeaders,
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  // GridCell取得と採点API。採点後の再取得は呼び出し側で制御する。
  async function fetchGridCells(areaId) {
    return requestJson(`/api/maps/areas/${areaId}/grids/`, {
      credentials: "same-origin",
    });
  }

  async function submitRating(gridId, payload) {
    return requestJson(`/api/maps/grids/${gridId}/ratings/`, {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(payload),
    });
  }

  async function submitBulkRating(payload) {
    return requestJson("/api/maps/grids/bulk-ratings/", {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(payload),
    });
  }

  // MapArea自体の削除API。危険操作の確認は画面側で行う。
  async function deleteArea(areaId) {
    return requestJson(`/api/maps/areas/${areaId}/`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: csrfHeaders(),
    });
  }

  // 共有相手の一覧・追加・解除を詳細画面から扱うためのAPI群。
  async function fetchShares(areaId) {
    return requestJson(`/api/maps/areas/${areaId}/shares/`, {
      credentials: "same-origin",
    });
  }

  async function addShare(areaId, payload) {
    return requestJson(`/api/maps/areas/${areaId}/shares/`, {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(payload),
    });
  }

  async function deleteShare(areaId, shareId) {
    return requestJson(`/api/maps/areas/${areaId}/shares/${shareId}/`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: csrfHeaders(),
    });
  }

  window.GridDetailApi = {
    fetchGridCells,
    submitRating,
    submitBulkRating,
    deleteArea,
    fetchShares,
    addShare,
    deleteShare,
  };
})();
