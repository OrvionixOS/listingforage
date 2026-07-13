import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { IMPROVE_ACTIONS } from "@/lib/categories";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function ImproveBar({ listingId }: { listingId: string }) {
  const qc = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);

  const run = async (action: string) => {
    setPending(action);
    try {
      await api.improve(listingId, { action });
      await qc.invalidateQueries({ queryKey: ["listing", listingId] });
      await qc.invalidateQueries({ queryKey: ["listings"] });
      toast.success("Listing improved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Improvement failed");
    } finally {
      setPending(null);
    }
  };

  return (
    <Card className="p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Wand2 className="h-4 w-4 text-primary" /> Improve this listing</h3>
      <div className="flex flex-wrap gap-2">
        {IMPROVE_ACTIONS.map((a) => (
          <Button key={a.key} variant="outline" size="sm" disabled={!!pending} onClick={() => run(a.key)}>
            {pending === a.key && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {a.label}
          </Button>
        ))}
      </div>
    </Card>
  );
}
