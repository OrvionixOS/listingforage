const TOKEN_KEY = "lf_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    body: form ? form : body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("lf:logout"));
  }
  const isText = res.headers.get("content-type")?.includes("text/plain");
  const data = isText ? await res.text() : await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

export const api = {
  register: (email, password) => request("/api/auth/register", { method: "POST", body: { email, password } }),
  login: (email, password) => request("/api/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/api/auth/me"),
  listings: () => request("/api/listings"),
  listing: (id) => request(`/api/listings/${id}`),
  deleteListing: (id) => request(`/api/listings/${id}`, { method: "DELETE" }),
  generate: (payload) => request("/api/listings/generate", { method: "POST", body: payload }),
  exportFmt: (id, fmt) => request(`/api/listings/${id}/export/${fmt}`),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/listings/uploads", { method: "POST", form });
  },
  upload: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/listings/uploads", {
      method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: fd,
    });
    if (!res.ok) throw new Error((await res.json()).detail || "upload failed");
    return res.json();
  },
  intakeAnalyze: (image_ids) =>
    request("/api/listings/intake/analyze", { method: "POST", body: { image_ids } }),
  overview: () => request("/api/workspace/overview"),
  notifications: () => request("/api/workspace/notifications"),
  markRead: (ids) => request("/api/workspace/notifications/read", { method: "POST", body: { ids } }),
  brand: () => request("/api/workspace/brand"),
  saveBrand: (body) => request("/api/workspace/brand", { method: "PUT", body }),
  bulkGenerate: (items) => request("/api/workspace/bulk/generate", { method: "POST", body: { items } }),
  bulkStatus: (batchId) => request(`/api/workspace/bulk/${batchId}`),
  editListing: (id, body) => request(`/api/listings/${id}`, { method: "PATCH", body }),
  assist: (id, body) => request(`/api/listings/${id}/assist`, { method: "POST", body }),
  quality: (id) => request(`/api/listings/${id}/quality`),
  seo: (id) => request(`/api/listings/${id}/seo`),
  journey: (id) => request(`/api/listings/${id}/journey`),
  reorderImages: (id, order) => request(`/api/listings/${id}/images/reorder`, { method: "POST", body: { order } }),
  imageVersions: (id, slot) => request(`/api/listings/${id}/images/${slot}/versions`),
  restoreVersion: (id, slot, imageId) =>
    request(`/api/listings/${id}/images/${slot}/restore/${imageId}`, { method: "POST" }),
  regenerateCustom: (id, slot, prompt) =>
    request(`/api/listings/${id}/images/${slot}/regenerate_custom`, { method: "POST", body: { prompt } }),
  versionBlob: async (id, slot, imageId) => {
    const res = await fetch(`/api/listings/${id}/images/${slot}/versions/${imageId}/file`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("version fetch failed");
    return URL.createObjectURL(await res.blob());
  },
  download: async (id, fmt) => {
    const res = await fetch(`/api/listings/${id}/export/${fmt}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("export failed");
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `listing.${fmt}`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  },
  images: (id) => request(`/api/listings/${id}/images`),
  imageBlob: async (id, slot) => {
    const res = await fetch(`/api/listings/${id}/images/${slot}/file`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("image fetch failed");
    return URL.createObjectURL(await res.blob());
  },
  regenerateImage: (id, slot) => request(`/api/listings/${id}/images/${slot}/regenerate`, { method: "POST" }),
  imageLogs: (id, slot) => request(`/api/listings/${id}/images/${slot}/logs`),
  etsyStatus: () => request("/api/etsy/status"),
  etsyConnect: () => request("/api/etsy/connect"),
  etsyGate: (id) => request(`/api/etsy/listings/${id}/gate`),
  etsyPublish: (id, body) => request(`/api/etsy/listings/${id}/publish`, { method: "POST", body }),
  etsyMetrics: () => request("/api/etsy/metrics"),
  etsyMetricsSync: () => request("/api/etsy/metrics/sync", { method: "POST" }),
  etsyCompetitive: (id) => request(`/api/etsy/listings/${id}/competitive`),
  plans: () => request("/api/billing/plans"),
  quota: () => request("/api/billing/quota"),
  checkout: (plan) => request("/api/billing/checkout", { method: "POST", body: { plan } }),
};
