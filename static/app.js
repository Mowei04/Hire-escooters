function extractErrorMessage(payload, fallback) {
  if (payload && payload.error && payload.error.message) return payload.error.message;
  if (payload && payload.message) return payload.message;
  return fallback;
}

function ensureToastContainer() {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.className = "toast-container-custom";
    document.body.appendChild(container);
  }
  return container;
}

function showToast(message, type = "danger") {
  const container = ensureToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast-item toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("toast-hide");
    setTimeout(() => toast.remove(), 300);
  }, 2600);
}

async function parseResponseBody(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return { message: text };
}

async function apiRequest(url, options = {}) {
  const {
    suppress401Redirect = false,
    suppress403Toast = false,
    json,
    headers,
    ...rest
  } = options;

  const requestOptions = {
    credentials: "same-origin",
    ...rest,
    headers: {
      ...(headers || {}),
    },
  };

  if (json !== undefined) {
    requestOptions.method = requestOptions.method || "POST";
    requestOptions.headers["Content-Type"] = "application/json";
    requestOptions.body = JSON.stringify(json);
  }

  const response = await fetch(url, requestOptions);
  const payload = await parseResponseBody(response);
  let alreadyNotified = false;

  if (response.status === 401 && !suppress401Redirect) {
    showToast("Session expired. Redirecting to login...", "warning");
    alreadyNotified = true;
    setTimeout(() => {
      window.location.href = "/customer/login";
    }, 500);
  }

  if (response.status === 403 && !suppress403Toast) {
    showToast("You do not have permission to access this resource.", "warning");
    alreadyNotified = true;
  }

  if (!response.ok) {
    throw {
      status: response.status,
      payload,
      alreadyNotified,
      message: extractErrorMessage(payload, `Request failed with status ${response.status}`),
    };
  }

  return payload;
}

function formatMoney(value) {
  return `$${Number(value).toFixed(2)}`;
}

window.apiRequest = apiRequest;
window.showToast = showToast;
window.extractErrorMessage = extractErrorMessage;
window.formatMoney = formatMoney;
