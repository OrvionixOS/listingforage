import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Wand2, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { api } from "@/lib/api";
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

function Generate() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [category, setCategory] = useState<string>("");
  const [style, setStyle] = useState<string>("Auto-detect");
  const [audience, setAudience] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [keywords, setKeywords] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);

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
      <PageHeader title="Generate a Listing" description="Tell us about your digital product. Our AI handles the research, SEO, copywriting, brand and image strategy." />
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
