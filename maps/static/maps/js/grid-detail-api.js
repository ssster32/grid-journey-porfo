(() => {
  "use strict";

  const utils = window.GridDetailUtils;
  if (!utils) {
    console.error("GridDetailUtils is not loaded.");
    return;
  }

  const { getCookie, readResponse, errorText } = utils;

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await readResponse(response);

    if (!response.ok) {
      throw new Error(errorText(response, data));
    }

    return data;
  }

  function csrfHeaders(extraHeaders = {}) {
    return {
      ...extraHeaders,
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

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

  async function deleteArea(areaId) {
    return requestJson(`/api/maps/areas/${areaId}/`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: csrfHeaders(),
    });
  }

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
