import { useState } from "react";
import { Copy, Check, Target, Users, Lightbulb, Gift, Crown, Quote, MessageSquare, ShieldAlert, TrendingUp, Swords, Sparkles, Palette, Type, Layers, DollarSign, Tag, Hash } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreRing } from "@/components/score-ring";
import { scoreColor, scoreLabel } from "@/lib/score";
import { SCORE_LABELS, type ListingResult } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          toast.success("Copied to clipboard");
          setTimeout(() => setDone(false), 1500);
        } catch {
          toast.error("Couldn't copy");
        }
      }}
    >
      {done ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {label}
    </Button>
  );
}

export function SectionCard({
  title,
  icon: Icon,
  action,
  children,
  className,
}: {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("p-5 sm:p-6", className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-display text-base font-semibold">
          {Icon && <Icon className="h-4 w-4 text-primary" />}
          {title}
        </h3>
        {action}
      </div>
      {children}
    </Card>
  );
}

export function Chips({ items }: { items?: string[] }) {
  if (!items?.length) return <p className="text-sm text-muted-foreground">Not available.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((t, i) => (
        <Badge key={i} variant="secondary" className="font-normal">
          {t}
        </Badge>
      ))}
    </div>
  );
}

function Bullets({ items }: { items?: string[] }) {
  if (!items?.length) return <p className="text-sm text-muted-foreground">Not available.</p>;
  return (
    <ul className="space-y-2">
      {items.map((t, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

function Stat({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value?: string }) {
  return (
    <div className="rounded-xl border border-border bg-secondary/40 p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-primary" /> {label}
      </div>
      <p className="mt-2 text-sm text-foreground">{value || "—"}</p>
    </div>
  );
}

export function ScoreBreakdown({ result }: { result: ListingResult }) {
  const s = result.scores;
  return (
    <SectionCard title="Listing Performance Score" icon={TrendingUp}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="flex flex-col items-center gap-2">
          <ScoreRing value={s?.overall ?? 0} size={128} label="Overall" />
          <Badge style={{ backgroundColor: scoreColor(s?.overall ?? 0), color: "white" }}>
            {scoreLabel(s?.overall ?? 0)}
          </Badge>
        </div>
        <div className="grid flex-1 gap-x-6 gap-y-3 sm:grid-cols-2">
          {SCORE_LABELS.filter((l) => l.key !== "overall").map((l) => {
            const v = (s?.[l.key] as number) ?? 0;
            return (
              <div key={l.key}>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{l.label}</span>
                  <span className="font-semibold" style={{ color: scoreColor(v) }}>{v}</span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full" style={{ width: `${v}%`, backgroundColor: scoreColor(v) }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {result.recommendations?.length > 0 && (
        <div className="mt-6 border-t border-border pt-5">
          <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-primary" /> Priority recommendations</h4>
          <Bullets items={result.recommendations} />
        </div>
      )}
    </SectionCard>
  );
}

export function ProductAnalysisSection({ result }: { result: ListingResult }) {
  const p = result.productAnalysis;
  return (
    <SectionCard title="Product Analysis" icon={Lightbulb}>
      <p className="text-sm text-muted-foreground">{p?.summary}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Stat icon={Users} label="Ideal buyer" value={p?.idealBuyer} />
        <Stat icon={Target} label="Buying motivation" value={p?.buyingMotivation} />
        <Stat icon={Sparkles} label="Emotional appeal" value={p?.emotionalAppeal} />
        <Stat icon={Gift} label="Gift potential" value={p?.giftPotential} />
        <Stat icon={Crown} label="Premium positioning" value={p?.premiumPositioning} />
        <Stat icon={Layers} label="Complexity" value={p?.complexity} />
      </div>
      <div className="mt-5 grid gap-5 sm:grid-cols-3">
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Use cases</h4><Chips items={p?.useCases} /></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Niches</h4><Chips items={p?.niches} /></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Seasonal</h4><Chips items={p?.seasonalOpportunities} /></div>
      </div>
    </SectionCard>
  );
}

export function ListingContentSection({ result }: { result: ListingResult }) {
  const d = result.description;
  return (
    <div className="space-y-5">
      <SectionCard title="Optimized Title" icon={Sparkles} action={<CopyButton text={result.titles?.best ?? ""} />}>
        <p className="text-lg font-medium">{result.titles?.best}</p>
        <p className="mt-2 text-xs text-muted-foreground">{result.titles?.reasoning}</p>
        {result.titles?.alternatives?.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Alternatives</h4>
            <ul className="space-y-2">
              {result.titles.alternatives.map((t, i) => (
                <li key={i} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-secondary/30 px-3 py-2 text-sm">
                  <span>{t}</span>
                  <CopyButton text={t} label="" />
                </li>
              ))}
            </ul>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Description" icon={MessageSquare} action={<CopyButton text={d?.fullText ?? ""} label="Copy full" />}>
        <pre className="max-h-[28rem] overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-secondary/30 p-4 font-sans text-sm text-muted-foreground">{d?.fullText}</pre>
        {d?.faq?.length > 0 && (
          <div className="mt-5">
            <h4 className="mb-3 text-sm font-semibold">FAQ</h4>
            <div className="space-y-3">
              {d.faq.map((f, i) => (
                <div key={i} className="rounded-lg border border-border p-3">
                  <p className="text-sm font-medium">{f.q}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{f.a}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard title="Etsy Tags (13)" icon={Tag} action={<CopyButton text={(result.tags ?? []).join(", ")} label="Copy all" />}>
          <Chips items={result.tags} />
        </SectionCard>
        <SectionCard title="Pricing Strategy" icon={DollarSign}>
          <div className="flex items-end gap-4">
            <div>
              <div className="font-display text-3xl font-bold text-primary">${result.pricing?.recommended}</div>
              <div className="text-xs text-muted-foreground">Recommended</div>
            </div>
            <div className="text-sm text-muted-foreground">Range ${result.pricing?.min}–${result.pricing?.max}</div>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{result.pricing?.strategy}</p>
        </SectionCard>
      </div>

      <SectionCard title="Keywords" icon={Hash}>
        <div className="grid gap-5 sm:grid-cols-3">
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Primary</h4><Chips items={result.keywords?.primary} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Secondary</h4><Chips items={result.keywords?.secondary} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Long-tail</h4><Chips items={result.keywords?.longTail} /></div>
        </div>
      </SectionCard>

      <SectionCard title="Listing Attributes" icon={Layers}>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Occasions</h4><Chips items={result.attributes?.occasions} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Themes</h4><Chips items={result.attributes?.themes} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Styles</h4><Chips items={result.attributes?.styles} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Colors</h4><Chips items={result.attributes?.colors} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Materials</h4><Chips items={result.attributes?.materials} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Categories</h4><Chips items={result.attributes?.categories} /></div>
        </div>
      </SectionCard>
    </div>
  );
}

export function MarketSection({ result }: { result: ListingResult }) {
  const m = result.marketResearch;
  return (
    <SectionCard title="Market Intelligence" icon={TrendingUp}>
      <p className="text-sm text-muted-foreground">{m?.overview}</p>
      <div className="mt-5 grid gap-5 sm:grid-cols-3">
        <div><h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Quote className="h-3.5 w-3.5" /> Competitor patterns</h4><Bullets items={m?.competitorPatterns} /></div>
        <div><h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><MessageSquare className="h-3.5 w-3.5" /> Customer language</h4><Bullets items={m?.customerLanguage} /></div>
        <div><h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><ShieldAlert className="h-3.5 w-3.5" /> Objections</h4><Bullets items={m?.objections} /></div>
      </div>
    </SectionCard>
  );
}

export function CompetitorSection({ result }: { result: ListingResult }) {
  const g = result.marketGap;
  const b = result.beatBestSellers;
  return (
    <div className="space-y-5">
      <SectionCard title="Market Gap Analysis" icon={Swords}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">What competitors do well</h4><Bullets items={g?.competitorsDoWell} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Competitor weaknesses</h4><Bullets items={g?.competitorWeaknesses} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">What customers respond to</h4><Bullets items={g?.customersRespondTo} /></div>
          <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Your differentiation</h4><Bullets items={g?.differentiation} /></div>
        </div>
        <div className="mt-5 rounded-xl border border-primary/30 bg-primary/5 p-4">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">Your stronger offer</h4>
          <p className="text-sm text-muted-foreground">{g?.strongerOffer}</p>
        </div>
      </SectionCard>
      <SectionCard title="How to Beat the Best Sellers" icon={Crown}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Stat icon={Target} label="Positioning" value={b?.positioning} />
          <Stat icon={Hash} label="Keyword strategy" value={b?.keywordStrategy} />
          <Stat icon={Sparkles} label="Visual strategy" value={b?.visualStrategy} />
        </div>
        <div className="mt-5">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Value propositions</h4>
          <Bullets items={b?.valueProps} />
        </div>
        <div className="mt-5 rounded-xl border border-primary/30 bg-primary/5 p-4">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">Why buyers choose this</h4>
          <p className="text-sm text-muted-foreground">{b?.whyChooseThis}</p>
        </div>
      </SectionCard>
    </div>
  );
}

export function BrandSection({ result }: { result: ListingResult }) {
  const b = result.brand;
  return (
    <SectionCard title="Brand Builder" icon={Palette}>
      <div className="rounded-xl border border-border bg-secondary/40 p-4">
        <p className="text-sm text-foreground">{b?.positioningStatement}</p>
        <p className="mt-2 text-xs text-muted-foreground">Ideal customer: {b?.idealCustomer}</p>
      </div>
      <div className="mt-5">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Personality</h4>
        <Chips items={b?.personality} />
      </div>
      <div className="mt-5">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Color palette</h4>
        <div className="flex flex-wrap gap-3">
          {b?.colors?.map((c, i) => (
            <div key={i} className="text-center">
              <div className="h-14 w-14 rounded-xl border border-border shadow-soft" style={{ backgroundColor: c.hex }} />
              <div className="mt-1.5 text-[11px] font-medium">{c.name}</div>
              <div className="text-[10px] text-muted-foreground">{c.hex}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <div><h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Type className="h-3.5 w-3.5" /> Typography</h4><Chips items={b?.typography} /></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Collection ideas</h4><Bullets items={b?.collectionIdeas} /></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Expansion ideas</h4><Bullets items={b?.expansionIdeas} /></div>
        <div><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Consistency guidelines</h4><Bullets items={b?.consistencyGuidelines} /></div>
      </div>
    </SectionCard>
  );
}

export function ImagesSection({ result }: { result: ListingResult }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {result.images?.map((img) => (
        <Card key={img.n} className="overflow-hidden p-0">
          <div className="flex items-center gap-3 border-b border-border bg-secondary/40 px-4 py-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg gradient-primary font-display text-sm font-bold text-primary-foreground">{img.n}</span>
            <div>
              <h4 className="text-sm font-semibold leading-tight">{img.title}</h4>
              <p className="text-xs text-muted-foreground">{img.purpose}</p>
            </div>
          </div>
          <div className="space-y-3 p-4 text-sm">
            <Field label="Psychology" value={img.psychology} />
            <Field label="Layout" value={img.layout} />
            <Field label="Copy overlay" value={img.copyOverlay} />
            <Field label="Design direction" value={img.designDirection} />
            <Field label="Mockup" value={img.mockup} />
            {img.cta && <Field label="CTA" value={img.cta} />}
          </div>
        </Card>
      ))}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}: </span>
      <span className="text-muted-foreground">{value}</span>
    </div>
  );
}