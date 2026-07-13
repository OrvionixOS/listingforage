import { queryOptions } from "@tanstack/react-query";
import { api } from "./api";
import type { ListingResult, ProductFile } from "./types";

export interface ProductRow {
  id: string;
  name: string;
  category: string | null;
  style: string | null;
  target_audience: string | null;
  notes: string | null;
  files: ProductFile[];
  thumbnail_url: string | null;
  created_at: string;
}

export interface ListingRow {
  id: string;
  product_id: string | null;
  title: string;
  status: string;
  score: number;
  saved: boolean;
  result: ListingResult;
  created_at: string;
  updated_at: string;
  products?: { name: string; category: string | null } | null;
}

export const productsQuery = queryOptions({
  queryKey: ["products"],
  queryFn: (): Promise<ProductRow[]> => api.products(),
});

export const listingsQuery = queryOptions({
  queryKey: ["listings"],
  queryFn: (): Promise<ListingRow[]> => api.listings(),
});

export const listingQuery = (id: string) =>
  queryOptions({
    queryKey: ["listing", id],
    queryFn: (): Promise<ListingRow | null> => api.listing(id).catch(() => null),
  });

export const profileQuery = queryOptions({
  queryKey: ["profile"],
  queryFn: () => api.profile(),
});
