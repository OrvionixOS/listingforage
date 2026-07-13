import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Wand2, Bookmark } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { ScoreRing } from "@/components/score-ring";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { listingsQuery } from "@/lib/queries";
import { scoreColor, scoreLabel } from "@/lib/score";

export const Route = createFileRoute("/_authenticated/listings/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(listingsQuery),
  component: ListingsIndex,
});

function ListingsIndex() {
  const { data: listings } = useSuspenseQuery(listingsQuery);
  return (
    <div>
      <PageHeader
        title="Your Listings"
        description="Every optimized listing you've generated, with its performance score."
        action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> New Listing</Link></Button>}
      />
      {listings.length === 0 ? (
        <EmptyState icon={Bookmark} title="No listings yet" description="Generate your first optimized Etsy listing to see it here." action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate">Generate a listing</Link></Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {listings.map((l) => (
            <Link key={l.id} to="/listings/$id" params={{ id: l.id }}>
              <Card className="flex items-center gap-4 p-4 transition-shadow hover:shadow-elegant">
                <ScoreRing value={l.score ?? 0} size={68} stroke={7} />
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm font-medium">{l.title}</p>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{l.products?.name ?? "Product"}</p>
                  <Badge className="mt-1.5" style={{ backgroundColor: scoreColor(l.score ?? 0), color: "white" }}>{scoreLabel(l.score ?? 0)}</Badge>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}