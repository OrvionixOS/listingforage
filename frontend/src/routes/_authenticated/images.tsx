import { createFileRoute } from "@tanstack/react-router";
import { Images } from "lucide-react";
import { LatestListingView } from "@/components/latest-listing";
import { ImagesSection } from "@/components/listing-sections";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/images")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: () => (
    <LatestListingView title="Image Studio" description="A 10-image visual merchandising plan engineered for clicks and conversions." icon={Images} render={(r) => <ImagesSection result={r} />} />
  ),
});