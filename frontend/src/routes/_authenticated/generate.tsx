import { useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Wand2, Loader2, Sparkles, ImagePlus, ScanSearch, Layers } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { CopyButton, Chips } from "@/components/listing-sections";
import { api, type ProductIdentification } from "@/lib/api";
import { PRODUCT_CATEGORIES, STYLE_OPTIONS } from "@/lib/categories";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/generate")({
  component: Generate,
});

const STEPS = ["Analyzing your product", "Researching the market", "Studying competitors", "Writing your optimized listing", "Planning 10 conversion images"];

interface Uploaded {
  uploadId: string;
  name: string;
  previewUrl: string;
}

function Generate() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  // images + identification
  const fileInput = useRef<HTMLInputElement>(null);
  const [images, setImages] = useState<Uploaded[]>([]);
  const [identifying, setIdentifying] = useState(false);
  const [ident, setIdent] = useState<ProductIdentification | null>(null);

  const [name, setName] = useState("");
  const [category, setCategory] = useState<string>("");
  const [style, setStyle] = useState<string>("Auto-detect");
  const [audience, setAudience] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [keywords, setKeywords] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);

  const addFiles = async (list: FileList | null) => {
    if (!list?.length) return;
    try {
      const added: Uploaded[] = [];
      for (const f of Array.from(list)) {
        const r = await api.uploadImage(f);
        added.push({ uploadId: r.upload_id, name: f.name, previewUrl: URL.createObjectURL(f) });
      }
      setImages((p) => [...p, ...added]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const identify = async () => {
    if (images.length === 0) return toast.error("Add your product images first.");
    setIdentifying(true);
    try {
      const r = await api.identify(images.map((i) => i.uploadId));
      setIdent(r);
      // auto-fill the brief from what the AI saw
      setName(r.suggested_name);
      if (PRODUCT_CATEGORIES.includes(r.category as (typeof PRODUCT_CATEGORIES)[number])) setCategory(r.category);
      if (STYLE_OPTIONS.includes(r.style as (typeof STYLE_OPTIONS)[number])) setStyle(r.style);
      setAudience(r.target_buyers.join(", "));
      setKeywords(r.tags.join(", "));
      setNotes(r.observed_details);
      toast.success("Product identified — brief filled in for you.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Image analysis failed");
    } finally {
      setIdentifying(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return toast.error("Give your product a name.");
    setBusy(true);
    setStep(0);
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2200);
    try {
      const product = await api.createProduct({
        name: name.trim(),
        category: category || null,
        style,
        target_audience: audience || null,
        notes: notes || null,
        upload_ids: images.map((i) => i.uploadId),
      });

      const res = await api.generate({ product_id: product.id, competitors, keywords });
      await qc.invalidateQueries();
      toast.success("Your optimized listing is ready!");
      navigate({ to: "/listings/$id", params: { id: res.listing_id } });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Generation failed");
      setBusy(false);
    } finally {
      clearInterval(timer);
    }
  };

  if (busy) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="relative">
          <div className="grid h-20 w-20 place-items-center rounded-2xl gradient-primary shadow-glow">
            <Sparkles className="h-9 w-9 text-primary-foreground" />
          </div>
        </div>
        <h2 className="mt-6 font-display text-xl font-bold">Building your growth strategy</h2>
        <div className="mt-6 w-full max-w-sm space-y-2.5">
          {STEPS.map((s, i) => (
            <div key={s} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors ${i <= step ? "border-primary/40 bg-primary/5 text-foreground" : "border-border text-muted-foreground"}`}>
              {i < step ? <span className="text-primary">✓</span> : i === step ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <span className="h-4 w-4" />}
              {s}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Generate a Listing" description="Drop in your product images — the AI identifies what it is, positions it, and handles the research, SEO, copywriting, brand and image strategy." />

      {/* Step 1 — images + identification */}
      <Card className="mb-5 p-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <ImagePlus className="h-4 w-4 text-primary" /> Product images
          <span className="font-normal text-muted-foreground">— let the AI see what you're selling</span>
        </h3>
        <div
          className="mt-4 grid cursor-pointer place-items-center rounded-xl border border-dashed border-border bg-secondary/30 px-6 py-10 text-center text-sm text-muted-foreground transition-colors hover:bg-secondary/50"
          role="button"
          tabIndex={0}
          onClick={() => fileInput.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addFiles(e.dataTransfer.files);
          }}
        >
          {images.length === 0
            ? "Tap to choose your product images, or drag them here (JPG / PNG / WebP)"
            : `${images.length} image${images.length > 1 ? "s" : ""} added — tap to add more`}
        </div>
        <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={(e) => addFiles(e.target.files)} />
        {images.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {images.slice(0, 12).map((f) => (
              <img key={f.uploadId} src={f.previewUrl} alt={f.name} className="h-16 w-16 rounded-lg border border-border object-cover" />
            ))}
            {images.length > 12 && <span className="text-xs text-muted-foreground">+{images.length - 12} more</span>}
          </div>
        )}
        <Button type="button" className="mt-4 gradient-primary text-primary-foreground shadow-glow hover:opacity-90" disabled={identifying || images.length === 0} onClick={identify}>
          {identifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
          {identifying ? "Looking at your images…" : "Identify my product"}
        </Button>
      </Card>

      {/* Identification result */}
      {ident && (
        <Card className="mb-5 space-y-5 p-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-lg gradient-primary text-primary-foreground">
                <Sparkles className="h-4 w-4" />
              </span>
              <h3 className="font-display text-base font-semibold">{ident.product_type}</h3>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{ident.positioning}</p>
          </div>

          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-primary">Strong Etsy title</h4>
                <p className="mt-1 text-sm font-medium">{ident.seo_title}</p>
              </div>
              <CopyButton text={ident.seo_title} />
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Keywords (13 Etsy tags)</h4>
                <CopyButton text={ident.tags.join(", ")} label="Copy all" />
              </div>
              <Chips items={ident.tags} />
            </div>
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Who this attracts</h4>
              <Chips items={ident.target_buyers} />
            </div>
          </div>

          <div>
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Layers className="h-3.5 w-3.5" /> Build a shop around this style
            </h4>
            <ul className="space-y-1.5">
              {ident.collection_ideas.map((c, i) => (
                <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  <span>{c}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground">{ident.shop_branding_note}</p>
          </div>
        </Card>
      )}

      {/* Step 2 — the brief (auto-filled by identification) */}
      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-3">
        <Card className="space-y-4 p-6 lg:col-span-2">
          <div className="space-y-2">
            <Label htmlFor="name">Product name *</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Minimalist Wedding Invitation Template" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger><SelectValue placeholder="Auto-detect" /></SelectTrigger>
                <SelectContent>
                  {PRODUCT_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Style</Label>
              <Select value={style} onValueChange={setStyle}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STYLE_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="audience">Target audience <span className="text-muted-foreground">(optional)</span></Label>
            <Input id="audience" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="e.g. Brides planning a modern minimalist wedding" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Product details / notes <span className="text-muted-foreground">(optional)</span></Label>
            <Textarea id="notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What's included, formats, sizes, what makes it special…" />
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="space-y-4 p-6">
            <h3 className="text-sm font-semibold">Competitive edge <span className="font-normal text-muted-foreground">(optional)</span></h3>
            <div className="space-y-2">
              <Label htmlFor="competitors" className="text-xs">Competitor listings or shops</Label>
              <Textarea id="competitors" rows={3} value={competitors} onChange={(e) => setCompetitors(e.target.value)} placeholder="Paste competitor titles, links or notes to beat…" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="keywords" className="text-xs">Existing keywords</Label>
              <Textarea id="keywords" rows={2} value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="Keywords you already rank for or target" />
            </div>
          </Card>
          <Button type="submit" size="lg" className="w-full gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
            <Wand2 className="h-4 w-4" /> Generate optimized listing
          </Button>
          <p className="text-center text-xs text-muted-foreground">Takes ~30 seconds. You'll get a full listing, brand plan, image strategy and score.</p>
        </div>
      </form>
    </div>
  );
}
