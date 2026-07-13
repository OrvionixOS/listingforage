import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Wand2, type LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { listingsQuery } from "@/lib/queries";
import type { ListingResult } from "@/lib/types";

export function LatestListingView({
  title,
  description,
  icon,
  render,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  render: (result: ListingResult) => ReactNode;
}) {
  const { data: listings } = useSuspenseQuery(listingsQuery);
  const latest = listings[0];
  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        action={latest && <Button asChild variant="outline"><Link to="/listings/$id" params={{ id: latest.id }}>Open full listing</Link></Button>}
      />
      {!latest ? (
        <EmptyState
          icon={icon}
          title="Generate a listing first"
          description="This analysis is produced when you generate a listing. Create one to unlock it."
          action={<Button asChild className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90"><Link to="/generate"><Wand2 className="h-4 w-4" /> Generate a listing</Link></Button>}
        />
      ) : (
        <div>
          <p className="mb-4 text-sm text-muted-foreground">Showing your most recent listing: <span className="font-medium text-foreground">{latest.title}</span></p>
          {render(latest.result)}
        </div>
      )}
    </div>
  );
}