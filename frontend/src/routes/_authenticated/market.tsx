import { createFileRoute } from "@tanstack/react-router";
import { TrendingUp } from "lucide-react";
import { LatestListingView } from "@/components/latest-listing";
import { MarketSection } from "@/components/listing-sections";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/market")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: () => (
    <LatestListingView title="Market Intelligence" description="Competitor patterns, customer language and buyer objections for your niche." icon={TrendingUp} render={(r) => <MarketSection result={r} />} />
  ),
});