// REST client for the FastAPI backend — replaces the Supabase integration.
import type { ListingResult } from "./types";
import type { ListingRow, ProductRow } from "./queries";

const TOKEN_KEY = "egai-token";

export const getToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* not json */
    }
    if (res.status === 401) clearToken();
    throw new Error(detail);
  }
  return (res.status === 204 ? null : await res.json()) as T;
}

export interface AuthUser {
  id: string;
  email: string;
}

export interface ProductIdentification {
  product_type: string;
  positioning: string;
  suggested_name: string;
  category: string;
  style: string;
  target_buyers: string[];
  seo_title: string;
  tags: string[];
  collection_ideas: string[];
  shop_branding_note: string;
  observed_details: string;
}

export const api = {
  // auth
  signUp: (email: string, password: string) =>
    request<{ access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  signIn: (email: string, password: string) =>
    request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<AuthUser>("/api/auth/me"),

  // uploads + vision identification
  uploadImage: async (file: File, kind: "image" | "asset" = "image") => {
    const form = new FormData();
    form.append("file", file);
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`/api/growth/uploads?kind=${kind}`, { method: "POST", headers, body: form });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        /* not json */
      }
      throw new Error(detail);
    }
    return (await res.json()) as { upload_id: string; filename: string };
  },
  identify: (uploadIds: string[]) =>
    request<ProductIdentification>("/api/growth/identify", {
      method: "POST",
      body: JSON.stringify({ upload_ids: uploadIds }),
    }),

  // products
  products: () => request<ProductRow[]>("/api/growth/products"),
  createProduct: (body: {
    name?: string | null;
    category?: string | null;
    style?: string | null;
    target_audience?: string | null;
    notes?: string | null;
    brand_name?: string | null;
    color_preferences?: string | null;
    file_link?: string | null;
    upload_ids?: string[];
    asset_upload_ids?: string[];
  }) => request<ProductRow>("/api/growth/products", { method: "POST", body: JSON.stringify(body) }),

  // generation
  generate: (body: { product_id: string; competitors?: string; keywords?: string }) =>
    request<{ listing_id: string; result: ListingResult }>("/api/growth/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  improve: (listingId: string, body: { action: string; instruction?: string }) =>
    request<{ listing_id: string; result: ListingResult }>(
      `/api/growth/listings/${listingId}/improve`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  // listings
  listings: () => request<ListingRow[]>("/api/growth/listings"),
  listing: (id: string) => request<ListingRow>(`/api/growth/listings/${id}`),
  deleteListing: (id: string) =>
    request<{ ok: boolean }>(`/api/growth/listings/${id}`, { method: "DELETE" }),

  // profile
  profile: () =>
    request<{ display_name: string | null; brand_name: string | null }>("/api/growth/profile"),
  updateProfile: (body: { display_name?: string | null; brand_name?: string | null }) =>
    request<{ display_name: string | null; brand_name: string | null }>("/api/growth/profile", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};

/** Session check used by route guards (no React state involved). */
export async function fetchMe(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  try {
    return await api.me();
  } catch {
    return null;
  }
}
