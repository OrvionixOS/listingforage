import { createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { LatestListingView } from "@/components/latest-listing";
import { ScoreBreakdown } from "@/components/listing-sections";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/seo")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: () => (
    <LatestListingView title="SEO Analyzer" description="A 0–100 performance score across 10 dimensions with priority fixes." icon={Search} render={(r) => <ScoreBreakdown result={r} />} />
  ),
});