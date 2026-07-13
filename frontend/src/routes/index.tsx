import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Wand2,
  TrendingUp,
  Palette,
  Images,
  Search,
  Swords,
  ArrowRight,
  Upload,
  BarChart3,
  Sparkles,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  component: Landing,
});

const FEATURES = [
  { icon: Wand2, title: "Complete Listing Generator", body: "Titles, a conversion description, 13 tags, keywords and every attribute — done for you." },
  { icon: TrendingUp, title: "Market Intelligence", body: "Competitor patterns, customer language, objections and a clear market-gap analysis." },
  { icon: Swords, title: "Beat the Best Sellers", body: "A concrete strategy for why a buyer chooses you over today's top listings." },
  { icon: Images, title: "10-Image Visual Plan", body: "A merchandising plan for every listing image with layout, copy and mockup direction." },
  { icon: Palette, title: "Brand Builder", body: "Positioning, palette, typography and product-collection ideas to scale your shop." },
  { icon: Search, title: "SEO + Performance Score", body: "A 0–100 listing score across 10 dimensions with specific ways to improve it." },
];

const STEPS = [
  { icon: Upload, title: "Upload your product", body: "Drop in printables, planners, SVGs, templates, fonts or bundles." },
  { icon: Sparkles, title: "AI does the strategy", body: "It analyzes the product, researches the market and studies competitors." },
  { icon: BarChart3, title: "Launch to win", body: "Get a full listing, image plan, brand plan and a competitive score." },
];

function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost">
              <Link to="/auth">Sign in</Link>
            </Button>
            <Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
              <Link to="/auth">Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden gradient-hero">
        <div className="mx-auto max-w-4xl px-4 py-24 text-center sm:px-6 sm:py-32">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> AI-powered Etsy Listing Intelligence
          </span>
          <h1 className="mt-6 font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
            Launch Etsy listings that <span className="text-gradient">beat the best sellers</span>.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Upload your product. The AI finds the best-selling competitors — then builds your entire
            Etsy listing to compete: positioning, SEO, pricing, brand and a 10-image conversion plan.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
              <Link to="/auth">
                Optimize my product <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/auth">See how it works</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grid gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <div key={s.title} className="rounded-2xl border border-border bg-card p-6 shadow-soft">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-secondary text-primary">
                  <s.icon className="h-5 w-5" />
                </span>
                <span className="font-display text-sm font-semibold text-muted-foreground">Step {i + 1}</span>
              </div>
              <h3 className="mt-4 font-display text-lg font-semibold">{s.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <h2 className="font-display text-3xl font-bold tracking-tight">An entire growth team in one tool</h2>
          <p className="mt-3 text-muted-foreground">
            Strategist, SEO specialist, copywriter, photographer and brand designer — working on every listing.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="group rounded-2xl border border-border bg-card p-6 transition-shadow hover:shadow-elegant">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
                <f.icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-display text-lg font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl border border-border gradient-hero p-10 text-center sm:p-16">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to out-sell the competition?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
            Upload your first product and see your optimized listing in minutes.
          </p>
          <Button asChild size="lg" className="mt-8 gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
            <Link to="/auth">
              Start free <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-border py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <Logo />
          <p className="text-xs text-muted-foreground">© {new Date().getFullYear()} Etsy Growth AI. Not affiliated with Etsy, Inc.</p>
        </div>
      </footer>
    </div>
  );
}
