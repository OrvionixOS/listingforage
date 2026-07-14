import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Images, Wand2 } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { RenderedGallery } from "@/components/rendered-gallery";
import { Button } from "@/components/ui/button";
import { listingsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/images")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: ImageStudio,
});

function ImageStudio() {
  const { data: listings } = useSuspenseQuery(listingsQuery);
  const latest = listings[0];
  return (
    <div>
      <PageHeader
        title="Image Studio"
        description="Finished, ready-to-upload Etsy listing images built from your product photos."
        action={latest && <Button asChild variant="outline"><Link to="/listings/$id" params={{ id: latest.id }}>Open full listing</Link></Button>}
      />
      {!latest ? (
        <EmptyState
          icon={Images}
          title="Generate a listing first"
          description="Your 10 Etsy listing images are created when you generate a listing. Create one to see them."
          action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> Generate a listing</Link></Button>}
        />
      ) : (
        <div>
          <p className="mb-4 text-sm text-muted-foreground">Showing your most recent listing: <span className="font-medium text-foreground">{latest.title}</span></p>
          <RenderedGallery listingId={latest.id} result={latest.result} />
        </div>
      )}
    </div>
  );
}
