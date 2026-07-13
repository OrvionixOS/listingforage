import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, MousePointerClick, PackagePlus, Network, Trophy, Swords } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type {
  CompetitorTeardown,
  ExpansionPlan,
  ListingResult,
  ThumbnailSimulation,
  UpgradePlan,
} from "@/lib/types";
import { SectionCard, Chips } from "@/components/listing-sections";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function RunButton({ label, busy, onClick }: { label: string; busy: boolean; onClick: () => void }) {
  return (
    <Button onClick={onClick} disabled={busy} className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
      {busy && <Loader2 className="h-4 w-4 animate-spin" />} {label}
    </Button>
  );
}

export function ThumbnailLab({ listingId, initial }: { listingId: string; initial?: ThumbnailSimulation }) {
  const qc = useQueryClient();
  const [sim, setSim] = useState<ThumbnailSimulation | undefined>(initial);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      setSim(await api.thumbnails(listingId));
      await qc.invalidateQueries({ queryKey: ["listing", listingId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard title="Thumbnail Optimization Simulator" icon={MousePointerClick}
      action={<RunButton label={sim ? "Re-run simulation" : "Simulate thumbnails"} busy={busy} onClick={run} />}>
      <p className="text-sm text-muted-foreground">
        The thumbnail is the biggest click factor. The AI designs 5–10 variations — text placement, product
        size, contrast, visual hierarchy — and predicts which earns the most clicks at 180px.
      </p>
      {sim && (
        <div className="mt-5 space-y-4">
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-primary">
              Winner: Version {sim.winner} — highest predicted click-through
            </h4>
            <p className="mt-1 text-sm text-muted-foreground">{sim.winnerRationale}</p>
            <p className="mt-2 text-xs text-muted-foreground">vs competitors: {sim.competitorComparison}</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {[...sim.variations].sort((a, b) => b.predictedCtr - a.predictedCtr).map((v) => (
              <Card key={v.n} className={cn("p-4", v.n === sim.winner && "border-primary/50 shadow-glow")}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">Version {v.n}{v.n === sim.winner && " 🏆"}</span>
                  <Badge variant="secondary" className="font-mono">{v.predictedCtr} CTR</Badge>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">{v.concept}</p>
                <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <p><span className="font-semibold">Text:</span> {v.textPlacement}</p>
                  <p><span className="font-semibold">Product size:</span> {v.productSize}</p>
                  <p><span className="font-semibold">Contrast:</span> {v.colorContrast}</p>
                  <p><span className="font-semibold">Hierarchy:</span> {v.visualHierarchy}</p>
                  <p><span className="font-semibold">Why:</span> {v.reasoning}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  );
}

export function UpgradeLab({ listingId, initial }: { listingId: string; initial?: UpgradePlan }) {
  const qc = useQueryClient();
  const [plan, setPlan] = useState<UpgradePlan | undefined>(initial);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      setPlan(await api.upgrades(listingId));
      await qc.invalidateQueries({ queryKey: ["listing", listingId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upgrade generation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard title="Product Upgrade Generator" icon={PackagePlus}
      action={<RunButton label={plan ? "Regenerate upgrades" : "Generate upgrades"} busy={busy} onClick={run} />}>
      <p className="text-sm text-muted-foreground">
        Turn the current product into a higher-value bundle — realistic add-ons that raise perceived value
        and justify a bigger price.
      </p>
      {plan && (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-secondary/40 p-4">
            <div>
              <div className="text-xs text-muted-foreground">Current</div>
              <div className="font-display text-2xl font-bold">${plan.priceFrom}</div>
            </div>
            <span className="text-2xl text-muted-foreground">→</span>
            <div>
              <div className="text-xs text-muted-foreground">Upgraded</div>
              <div className="font-display text-2xl font-bold text-primary">${plan.priceTo}</div>
            </div>
            <p className="min-w-48 flex-1 text-sm text-muted-foreground">{plan.pricingRationale}</p>
          </div>
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Current offer</h4>
            <p className="text-sm text-muted-foreground">{plan.currentOffer}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {plan.upgrades.map((u, i) => (
              <Card key={i} className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{u.addition}</span>
                  <Badge variant="secondary">{u.effort} effort</Badge>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">{u.whyItWorks}</p>
                <p className="mt-1 text-xs text-muted-foreground">Value impact: {u.valueImpact}</p>
              </Card>
            ))}
          </div>
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-primary">The upgraded offer</h4>
            <p className="mt-1 text-sm text-muted-foreground">{plan.upgradedOffer}</p>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

export function ExpansionLab({ listingId, initial }: { listingId: string; initial?: ExpansionPlan }) {
  const qc = useQueryClient();
  const [plan, setPlan] = useState<ExpansionPlan | undefined>(initial);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      setPlan(await api.expansion(listingId));
      await qc.invalidateQueries({ queryKey: ["listing", listingId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Expansion planning failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SectionCard title="Product Expansion Engine" icon={Network}
      action={<RunButton label={plan ? "Regenerate catalog" : "Create related products"} busy={busy} onClick={run} />}>
      <p className="text-sm text-muted-foreground">
        One product becomes a catalog: 12–20 related products for the same buyer and aesthetic, with a
        launch order and cross-sell strategy.
      </p>
      {plan && (
        <div className="mt-5 space-y-4">
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-primary">Collection: {plan.collectionName}</h4>
            <p className="mt-1 text-sm text-muted-foreground">{plan.crossSellStrategy}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plan.ideas.map((idea, i) => (
              <Card key={i} className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold">{idea.name}</span>
                  <Badge variant="secondary" className="shrink-0">{idea.priceRange}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{idea.subcategory}</p>
                <p className="mt-1.5 text-sm text-muted-foreground">{idea.whyItSells}</p>
              </Card>
            ))}
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Launch first</h4>
            <ul className="space-y-1.5">
              {plan.launchOrder.map((l, i) => (
                <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/10 text-xs font-bold text-primary">{i + 1}</span>
                  <span>{l}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

export function TeardownCard({ teardown }: { teardown: CompetitorTeardown }) {
  const c = teardown.competitor;
  return (
    <SectionCard title="Built to beat this competitor" icon={Swords}
      action={teardown.data_source === "live_etsy_data"
        ? <Badge className="bg-primary text-primary-foreground">live Etsy data</Badge>
        : <Badge variant="secondary">modeled analysis</Badge>}>
      <div className="rounded-xl border border-border bg-secondary/40 p-4">
        <p className="text-sm font-medium">{c.title}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {c.price != null && <>Price: ${c.price} · </>}
          {c.imageCount != null && <>{c.imageCount} images · </>}
          {teardown.competitor_url && (
            <a href={teardown.competitor_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">view listing</a>
          )}
        </p>
        {c.tags.length > 0 && <div className="mt-2"><Chips items={c.tags.slice(0, 13)} /></div>}
      </div>
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Their strengths</h4>
          <ul className="space-y-1.5">{c.strengths.map((s, i) => <li key={i} className="text-sm text-muted-foreground">• {s}</li>)}</ul></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Their weaknesses</h4>
          <ul className="space-y-1.5">{c.weaknesses.map((s, i) => <li key={i} className="text-sm text-muted-foreground">• {s}</li>)}</ul></div>
      </div>
      {c.reviewSignals.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">What their reviews signal</h4>
          <Chips items={c.reviewSignals} />
        </div>
      )}
      <div className="mt-4">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Openings they leave</h4>
        <ul className="space-y-1.5">{teardown.gaps.map((g, i) => <li key={i} className="text-sm text-muted-foreground">• {g}</li>)}</ul>
      </div>
      <div className="mt-4 rounded-xl border border-primary/30 bg-primary/5 p-4">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
          <Trophy className="h-3.5 w-3.5" /> How this listing wins
        </h4>
        <p className="mt-1 text-sm text-muted-foreground">{teardown.positioningPlan}</p>
        <p className="mt-2 text-sm font-medium">Upgraded offer: <span className="font-normal text-muted-foreground">{teardown.upgradedOffer}</span></p>
      </div>
    </SectionCard>
  );
}

export function GrowthLab({ listingId, result }: { listingId: string; result: ListingResult }) {
  return (
    <div className="space-y-5">
      <ThumbnailLab listingId={listingId} initial={result.thumbnailSimulation} />
      <UpgradeLab listingId={listingId} initial={result.upgradePlan} />
      <ExpansionLab listingId={listingId} initial={result.expansionPlan} />
    </div>
  );
}
