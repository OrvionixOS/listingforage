import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ArrowLeft, FileWarning } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { ImproveBar } from "@/components/improve-bar";
import {
  ScoreBreakdown,
  ProductAnalysisSection,
  ListingContentSection,
  MarketSection,
  CompetitorSection,
  BrandSection,
  ImagesSection,
} from "@/components/listing-sections";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listingQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/listings/$id")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(listingQuery(params.id)),
  component: ListingDetail,
});

function ListingDetail() {
  const { id } = Route.useParams();
  const { data: listing } = useSuspenseQuery(listingQuery(id));

  if (!listing) {
    return (
      <EmptyState
        icon={FileWarning}
        title="Listing not found"
        description="This listing may have been deleted."
        action={<Button asChild><Link to="/listings">Back to listings</Link></Button>}
      />
    );
  }

  const result = listing.result;

  return (
    <div>
      <Button asChild variant="ghost" size="sm" className="mb-3 -ml-2"><Link to="/listings"><ArrowLeft className="h-4 w-4" /> All listings</Link></Button>
      <PageHeader title={listing.title} description={listing.products?.name ? `Product: ${listing.products.name}` : undefined} />

      <div className="mb-6"><ImproveBar listingId={listing.id} /></div>

      <Tabs defaultValue="listing">
        <TabsList className="mb-5 flex h-auto flex-wrap justify-start gap-1">
          <TabsTrigger value="listing">Listing</TabsTrigger>
          <TabsTrigger value="score">Score</TabsTrigger>
          <TabsTrigger value="market">Market</TabsTrigger>
          <TabsTrigger value="competitors">Competitors</TabsTrigger>
          <TabsTrigger value="brand">Brand</TabsTrigger>
          <TabsTrigger value="images">Images</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>
        <TabsContent value="listing"><ListingContentSection result={result} /></TabsContent>
        <TabsContent value="score"><ScoreBreakdown result={result} /></TabsContent>
        <TabsContent value="market"><MarketSection result={result} /></TabsContent>
        <TabsContent value="competitors"><CompetitorSection result={result} /></TabsContent>
        <TabsContent value="brand"><BrandSection result={result} /></TabsContent>
        <TabsContent value="images"><ImagesSection result={result} /></TabsContent>
        <TabsContent value="analysis"><ProductAnalysisSection result={result} /></TabsContent>
      </Tabs>
    </div>
  );
}