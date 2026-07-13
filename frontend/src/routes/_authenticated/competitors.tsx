import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useSuspenseQuery, useQueryClient } from "@tanstack/react-query";
import { Swords, Loader2, Wand2, Trophy } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { CompetitorSection } from "@/components/listing-sections";
import { TeardownCard } from "@/components/growth-lab";
import { api } from "@/lib/api";
import { listingsQuery, productsQuery } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/competitors")({
  loader: async ({ context }) => {
    await Promise.all([
      context.queryClient.ensureQueryData(listingsQuery),
      context.queryClient.ensureQueryData(productsQuery),
    ]);
  },
  component: Competitors,
});

function BeatBestSeller() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: products } = useSuspenseQuery(productsQuery);
  const [productId, setProductId] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!productId) return toast.error("Pick which of your products should beat them.");
    if (!/etsy\.com\/.*listing\//.test(url)) return toast.error("Paste a full Etsy listing link (etsy.com/listing/…).");
    setBusy(true);
    try {
      const res = await api.beatCompetitor({ product_id: productId, competitor_url: url.trim() });
      await qc.invalidateQueries();
      toast.success("Competitor torn down — your listing was rebuilt to beat it.");
      navigate({ to: "/listings/$id", params: { id: res.listing_id } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Beat-competitor run failed");
      setBusy(false);
    }
  };

  return (
    <Card className="mb-6 p-6">
      <h3 className="flex items-center gap-2 font-display text-base font-semibold">
        <Trophy className="h-4 w-4 text-primary" /> Make it better than the best seller
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Paste a competitor's Etsy listing link. The AI analyzes their images, keywords, reviews and
        weaknesses — then rebuilds your entire listing to outperform it.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-xs">Your product</Label>
            <Select value={productId} onValueChange={setProductId}>
              <SelectTrigger><SelectValue placeholder="Choose a product" /></SelectTrigger>
              <SelectContent>
                {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cu" className="text-xs">Competitor listing URL</Label>
            <Input id="cu" value={url} onChange={(e) => setUrl(e.target.value)}
                   placeholder="https://www.etsy.com/listing/123456789/…" />
          </div>
        </div>
        <Button onClick={run} disabled={busy} className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Swords className="h-4 w-4" />}
          {busy ? "Analyzing & rebuilding…" : "Beat this listing"}
        </Button>
      </div>
      {products.length === 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          You need a product first — <Link to="/generate" className="text-primary hover:underline">create one here</Link>.
        </p>
      )}
    </Card>
  );
}

function Competitors() {
  const { data: listings } = useSuspenseQuery(listingsQuery);
  const latest = listings[0];
  return (
    <div>
      <PageHeader
        title="Competitor Analysis"
        description="Find the market gap and the strategy to beat today's best sellers."
        action={latest && <Button asChild variant="outline"><Link to="/listings/$id" params={{ id: latest.id }}>Open full listing</Link></Button>}
      />
      <BeatBestSeller />
      {!latest ? (
        <EmptyState
          icon={Swords}
          title="Generate a listing first"
          description="This analysis is produced when you generate a listing. Create one to unlock it."
          action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> Generate a listing</Link></Button>}
        />
      ) : (
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">
            Showing your most recent listing: <span className="font-medium text-foreground">{latest.title}</span>
          </p>
          {latest.result.competitorTeardown && <TeardownCard teardown={latest.result.competitorTeardown} />}
          <CompetitorSection result={latest.result} />
        </div>
      )}
    </div>
  );
}
