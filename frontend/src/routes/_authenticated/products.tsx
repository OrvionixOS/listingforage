import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Package, Wand2 } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { productsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/products")({
  loader: ({ context }) => context.queryClient.ensureQueryData(productsQuery),
  component: Products,
});

function Products() {
  const { data: products } = useSuspenseQuery(productsQuery);
  return (
    <div>
      <PageHeader
        title="My Products"
        description="Every digital product you've added to Etsy Growth AI."
        action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> New Listing</Link></Button>}
      />
      {products.length === 0 ? (
        <EmptyState icon={Package} title="No products yet" description="Add your first digital product when you generate a listing." action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate">Add a product</Link></Button>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <Card key={p.id} className="p-5">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-display font-semibold leading-tight">{p.name}</h3>
                {p.category && <Badge variant="secondary" className="shrink-0 font-normal">{p.category}</Badge>}
              </div>
              {p.target_audience && <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{p.target_audience}</p>}
              <p className="mt-3 text-xs text-muted-foreground">Added {new Date(p.created_at).toLocaleDateString()}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}