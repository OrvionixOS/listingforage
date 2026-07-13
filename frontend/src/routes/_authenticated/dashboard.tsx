import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Wand2, Package, Bookmark, TrendingUp, ArrowRight, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { ScoreRing } from "@/components/score-ring";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { productsQuery, listingsQuery } from "@/lib/queries";
import { scoreColor, scoreLabel } from "@/lib/score";

export const Route = createFileRoute("/_authenticated/dashboard")({
  loader: async ({ context }) => {
    await Promise.all([
      context.queryClient.ensureQueryData(productsQuery),
      context.queryClient.ensureQueryData(listingsQuery),
    ]);
  },
  component: Dashboard,
});

function Dashboard() {
  const { data: products } = useSuspenseQuery(productsQuery);
  const { data: listings } = useSuspenseQuery(listingsQuery);

  const avg = listings.length
    ? Math.round(listings.reduce((a, l) => a + (l.score ?? 0), 0) / listings.length)
    : 0;
  const best = listings.reduce((a, l) => Math.max(a, l.score ?? 0), 0);

  const stats = [
    { label: "Products", value: products.length, icon: Package },
    { label: "Listings generated", value: listings.length, icon: Wand2 },
    { label: "Avg. score", value: avg, icon: TrendingUp },
    { label: "Best score", value: best, icon: Sparkles },
  ];

  return (
    <div>
      <PageHeader
        title="Growth Dashboard"
        description="Your AI Etsy command center — track products, listings and performance."
        action={
          <Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
            <Link to="/generate"><Wand2 className="h-4 w-4" /> New Listing</Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label} className="p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{s.label}</span>
              <s.icon className="h-4 w-4 text-primary" />
            </div>
            <div className="mt-2 font-display text-3xl font-bold">{s.value}</div>
          </Card>
        ))}
      </div>

      <div className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Recent listings</h2>
          {listings.length > 0 && (
            <Button asChild variant="ghost" size="sm"><Link to="/listings">View all <ArrowRight className="h-4 w-4" /></Link></Button>
          )}
        </div>
        {listings.length === 0 ? (
          <EmptyState
            icon={Wand2}
            title="No listings yet"
            description="Upload a digital product and generate your first optimized, competition-beating Etsy listing."
            action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> Generate a listing</Link></Button>}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {listings.slice(0, 6).map((l) => (
              <Link key={l.id} to="/listings/$id" params={{ id: l.id }}>
                <Card className="flex items-center gap-4 p-4 transition-shadow hover:shadow-elegant">
                  <ScoreRing value={l.score ?? 0} size={64} stroke={7} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{l.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{l.products?.name ?? "Product"}</p>
                    <Badge className="mt-1.5" style={{ backgroundColor: scoreColor(l.score ?? 0), color: "white" }}>{scoreLabel(l.score ?? 0)}</Badge>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}