import { createFileRoute } from "@tanstack/react-router";
import { Swords } from "lucide-react";
import { LatestListingView } from "@/components/latest-listing";
import { CompetitorSection } from "@/components/listing-sections";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/competitors")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: () => (
    <LatestListingView title="Competitor Analysis" description="Find the market gap and the strategy to beat today's best sellers." icon={Swords} render={(r) => <CompetitorSection result={r} />} />
  ),
});