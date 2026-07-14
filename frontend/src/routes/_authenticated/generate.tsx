import { useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Wand2, Loader2, Sparkles, ImagePlus, ScanSearch, Layers, FileArchive, Palette } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { CopyButton, Chips } from "@/components/listing-sections";
import { api, type ProductIdentification } from "@/lib/api";
import { CATEGORY_GROUPS, STYLE_OPTIONS, PRODUCT_CATEGORIES } from "@/lib/categories";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/generate")({
  component: Generate,
});

const STEPS = ["Reading your product files", "Analyzing your product", "Researching the market", "Studying competitors", "Writing your optimized listing", "Planning 10 conversion images"];

interface Uploaded {
  uploadId: string;
  name: string;
  previewUrl?: string;
}

function Generate() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  // step 1 — product images (required)
  const imageInput = useRef<HTMLInputElement>(null);
  const [images, setImages] = useState<Uploaded[]>([]);
  const [identifying, setIdentifying] = useState(false);
  const [ident, setIdent] = useState<ProductIdentification | null>(null);

  // step 2 — product file (optional)
  const assetInput = useRef<HTMLInputElement>(null);
  const [assets, setAssets] = useState<Uploaded[]>([]);
  const [fileLink, setFileLink] = useState("");

  // step 3 — category
  const [category, setCategory] = useState<string>("");

  // step 4 — brand style (optional)
  const [brandName, setBrandName] = useState("");
  const [style, setStyle] = useState<string>("Auto-detect");
  const [colors, setColors] = useState("");

  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);

  const addImages = async (list: FileList | null) => {
    if (!list?.length) return;
    // each file is independent: one failure must not drop the rest of the batch
    let failed = 0;
    for (const f of Array.from(list)) {
      try {
        const r = await api.uploadImage(f);
        setImages((p) => [...p, { uploadId: r.upload_id, name: f.name, previewUrl: URL.createObjectURL(f) }]);
      } catch {
        failed += 1;
      }
    }
    if (failed) toast.error(`${failed} image${failed > 1 ? "s" : ""} couldn't be uploaded (unsupported type or too large).`);
  };

  const addAssets = async (list: FileList | null) => {
    if (!list?.length) return;
    let failed = 0;
    for (const f of Array.from(list)) {
      try {
        const r = await api.uploadImage(f, "asset");
        setAssets((p) => [...p, { uploadId: r.upload_id, name: f.name }]);
      } catch {
        failed += 1;
      }
    }
    if (failed) toast.error(`${failed} file${failed > 1 ? "s" : ""} couldn't be uploaded.`);
  };

  const identify = async () => {
    if (images.length === 0) return toast.error("Add your product images first.");
    setIdentifying(true);
    try {
      const r = await api.identify(images.map((i) => i.uploadId));
      setIdent(r);
      if (PRODUCT_CATEGORIES.includes(r.category)) setCategory(r.category);
      if (STYLE_OPTIONS.includes(r.style as (typeof STYLE_OPTIONS)[number])) setStyle(r.style);
      toast.success("Product identified.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Image analysis failed");
    } finally {
      setIdentifying(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (images.length === 0) return toast.error("Upload at least one product image.");
    if (!category) return toast.error("Choose the product category.");
    setBusy(true);
    setStep(0);
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2200);
    try {
      const product = await api.createProduct({
        name: ident?.suggested_name || null,
        category,
        style,
        target_audience: ident?.target_buyers?.join(", ") || null,
        notes: ident?.observed_details || null,
        brand_name: brandName || null,
        color_preferences: colors || null,
        file_link: fileLink || null,
        upload_ids: images.map((i) => i.uploadId),
        asset_upload_ids: assets.map((a) => a.uploadId),
      });

      const res = await api.generate({
        product_id: product.id,
        keywords: ident?.tags?.join(", ") || "",
      });
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
      <PageHeader title="Generate a Listing" description="Upload your product — the AI identifies what it is and creates the full listing, images plan, tags and pricing. No long forms." />

      <form onSubmit={submit} className="space-y-5">
        {/* Step 1 — product images (required) */}
        <Card className="p-6">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <ImagePlus className="h-4 w-4 text-primary" /> 1. Product images
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">Required</span>
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Cover image, pages/screenshots, design elements, variations, close-ups, existing mockups.
          </p>
          <div
            className="mt-4 grid cursor-pointer place-items-center rounded-xl border border-dashed border-border bg-secondary/30 px-6 py-10 text-center text-sm text-muted-foreground transition-colors hover:bg-secondary/50"
            role="button"
            tabIndex={0}
            onClick={() => imageInput.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && imageInput.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              addImages(e.dataTransfer.files);
            }}
          >
            {images.length === 0
              ? "Tap to choose your product images, or drag them here (JPG / PNG / WebP)"
              : `${images.length} image${images.length > 1 ? "s" : ""} added — tap to add more`}
          </div>
          <input ref={imageInput} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={(e) => addImages(e.target.files)} />
          {images.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {images.slice(0, 12).map((f) => (
                <img key={f.uploadId} src={f.previewUrl} alt={f.name} className="h-16 w-16 rounded-lg border border-border object-cover" />
              ))}
              {images.length > 12 && <span className="text-xs text-muted-foreground">+{images.length - 12} more</span>}
            </div>
          )}
          <Button type="button" variant="outline" className="mt-4" disabled={identifying || images.length === 0} onClick={identify}>
            {identifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
            {identifying ? "Looking at your images…" : "Identify my product"}
          </Button>

          {ident && (
            <div className="mt-5 space-y-4 rounded-xl border border-border bg-secondary/30 p-4">
              <div>
                <h4 className="font-display text-sm font-semibold">{ident.product_type}</h4>
                <p className="mt-1.5 text-sm text-muted-foreground">{ident.positioning}</p>
              </div>
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h5 className="text-xs font-semibold uppercase tracking-wide text-primary">Strong Etsy title</h5>
                    <p className="mt-1 text-sm font-medium">{ident.seo_title}</p>
                  </div>
                  <CopyButton text={ident.seo_title} />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Keywords (13 tags)</h5>
                    <CopyButton text={ident.tags.join(", ")} label="Copy" />
                  </div>
                  <Chips items={ident.tags} />
                </div>
                <div>
                  <h5 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Who this attracts</h5>
                  <Chips items={ident.target_buyers} />
                </div>
              </div>
              <div>
                <h5 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <Layers className="h-3.5 w-3.5" /> Build a shop around this style
                </h5>
                <ul className="space-y-1">
                  {ident.collection_ideas.map((c, i) => (
                    <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">{ident.shop_branding_note}</p>
              </div>
            </div>
          )}
        </Card>

        {/* Step 2 — product file (optional) */}
        <Card className="p-6">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FileArchive className="h-4 w-4 text-primary" /> 2. Product file
            <span className="font-normal text-muted-foreground">(optional — the AI reads it for listing accuracy)</span>
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            PDF, ZIP or SVG — so the AI knows exactly what's included, page/file counts, style and intended use.
          </p>
          <div
            className="mt-4 grid cursor-pointer place-items-center rounded-xl border border-dashed border-border bg-secondary/30 px-6 py-6 text-center text-sm text-muted-foreground transition-colors hover:bg-secondary/50"
            role="button"
            tabIndex={0}
            onClick={() => assetInput.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && assetInput.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              addAssets(e.dataTransfer.files);
            }}
          >
            {assets.length === 0
              ? "Tap to add the product file itself (PDF / ZIP / SVG)"
              : assets.map((a) => a.name).join(", ")}
          </div>
          <input ref={assetInput} type="file" accept=".pdf,.zip,.svg,application/pdf,application/zip,image/svg+xml" multiple hidden onChange={(e) => addAssets(e.target.files)} />
          <div className="mt-4 space-y-2">
            <Label htmlFor="filelink" className="text-xs">Or paste a link (e.g. Canva template link)</Label>
            <Input id="filelink" value={fileLink} onChange={(e) => setFileLink(e.target.value)} placeholder="https://www.canva.com/design/…" />
          </div>
        </Card>

        {/* Step 3 — category */}
        <Card className="p-6">
          <h3 className="text-sm font-semibold">3. Product category</h3>
          <div className="mt-3 max-w-md">
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger><SelectValue placeholder="Choose a category" /></SelectTrigger>
              <SelectContent className="max-h-80">
                {CATEGORY_GROUPS.map((g) => (
                  <SelectGroup key={g.label}>
                    <SelectLabel>{g.label}</SelectLabel>
                    {g.items.map((item) => (
                      <SelectItem key={item} value={`${g.label} / ${item}`}>{item}</SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </div>
        </Card>

        {/* Step 4 — brand style (optional) */}
        <Card className="p-6">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Palette className="h-4 w-4 text-primary" /> 4. Brand style
            <span className="font-normal text-muted-foreground">(optional)</span>
          </h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="brand" className="text-xs">Brand name</Label>
              <Input id="brand" value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="e.g. Luxe Surfaces" />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Preferred style</Label>
              <Select value={style} onValueChange={setStyle}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STYLE_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="colors" className="text-xs">Color preferences</Label>
              <Input id="colors" value={colors} onChange={(e) => setColors(e.target.value)} placeholder="e.g. gold, ivory, charcoal" />
            </div>
          </div>
        </Card>

        <div className="flex flex-col items-center gap-3">
          <Button type="submit" size="lg" className="w-full max-w-md gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
            <Wand2 className="h-4 w-4" /> Generate my Etsy listing
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            The AI creates the title, description, 13 tags, pricing and the 10-image Etsy listing plan from your product itself.
          </p>
        </div>
      </form>
    </div>
  );
}
