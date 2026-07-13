import { createFileRoute } from "@tanstack/react-router";
import { Palette } from "lucide-react";
import { LatestListingView } from "@/components/latest-listing";
import { BrandSection } from "@/components/listing-sections";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/brand")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: () => (
    <LatestListingView title="Brand Builder" description="Positioning, palette, typography and a plan to grow your shop into a brand." icon={Palette} render={(r) => <BrandSection result={r} />} />
  ),
});