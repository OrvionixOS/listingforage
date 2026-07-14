import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ArrowLeft, FileWarning, Loader2, PackageCheck } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { ImproveBar } from "@/components/improve-bar";
import { GrowthLab, TeardownCard } from "@/components/growth-lab";
import { RenderedGallery } from "@/components/rendered-gallery";
import {
  ScoreBreakdown,
  ProductAnalysisSection,
  ListingContentSection,
  MarketSection,
  CompetitorSection,
  BrandSection,
} from "@/components/listing-sections";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listingQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/listings/$id")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(listingQuery(params.id)),
  component: ListingDetail,
});

function PackageButton({ listingId, title }: { listingId: string; title: string }) {
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const { package: text } = await api.listingPackage(listingId);
      const blob = new Blob([text], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title.slice(0, 40).replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-etsy-package.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Listing package downloaded — everything ready to upload.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Package export failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button onClick={download} disabled={busy} className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageCheck className="h-4 w-4" />}
      Download listing package
    </Button>
  );
}

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
      <PageHeader
        title={listing.title}
        description={listing.products?.name ? `Product: ${listing.products.name}` : undefined}
        action={<PackageButton listingId={listing.id} title={listing.title} />}
      />

      <div className="mb-6"><ImproveBar listingId={listing.id} /></div>

      <Tabs defaultValue="listing">
        <TabsList className="mb-5 flex h-auto flex-wrap justify-start gap-1">
          <TabsTrigger value="listing">Listing</TabsTrigger>
          <TabsTrigger value="score">Score</TabsTrigger>
          <TabsTrigger value="market">Market</TabsTrigger>
          <TabsTrigger value="competitors">Competitors</TabsTrigger>
          <TabsTrigger value="brand">Brand</TabsTrigger>
          <TabsTrigger value="images">Images</TabsTrigger>
          <TabsTrigger value="growth">Growth Lab</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>
        <TabsContent value="listing"><ListingContentSection result={result} /></TabsContent>
        <TabsContent value="score"><ScoreBreakdown result={result} /></TabsContent>
        <TabsContent value="market"><MarketSection result={result} /></TabsContent>
        <TabsContent value="competitors">
          <div className="space-y-5">
            {result.competitorTeardown && <TeardownCard teardown={result.competitorTeardown} />}
            <CompetitorSection result={result} />
          </div>
        </TabsContent>
        <TabsContent value="brand"><BrandSection result={result} /></TabsContent>
        <TabsContent value="images"><RenderedGallery listingId={listing.id} result={result} /></TabsContent>
        <TabsContent value="growth"><GrowthLab listingId={listing.id} result={result} /></TabsContent>
        <TabsContent value="analysis"><ProductAnalysisSection result={result} /></TabsContent>
      </Tabs>
    </div>
  );
}
