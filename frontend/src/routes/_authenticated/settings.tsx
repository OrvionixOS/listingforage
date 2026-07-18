import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard-shell";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { profileQuery } from "@/lib/queries";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/settings")({
  component: Settings,
});

function Settings() {
  const { user, signOut } = useAuth();
  const qc = useQueryClient();
  const { data: profile } = useQuery(profileQuery);
  const [displayName, setDisplayName] = useState("");
  const [brandName, setBrandName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? "");
      setBrandName(profile.brand_name ?? "");
    }
  }, [profile]);

  const save = async () => {
    setBusy(true);
    try {
      await api.updateProfile({ display_name: displayName || null, brand_name: brandName || null });
      await qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success("Settings saved");
    } catch {
      toast.error("Could not save changes");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Settings" description="Manage your account and brand details." />
      <div className="grid max-w-xl gap-5">
        <Card className="space-y-4 p-6">
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={user?.email ?? ""} disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="dn">Display name</Label>
            <Input id="dn" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Your name" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bn">Shop / brand name</Label>
            <Input id="bn" value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="Your Etsy shop name" />
          </div>
          <Button onClick={save} disabled={busy} className="gradient-primary text-primary-foreground shadow-glow hover:opacity-90">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Save changes
          </Button>
        </Card>
        <EtsyCheckCard />
        <Card className="flex items-center justify-between p-6">
          <div>
            <h3 className="font-semibold">Sign out</h3>
            <p className="text-sm text-muted-foreground">Sign out of your account on this device.</p>
          </div>
          <Button variant="outline" onClick={() => signOut()}>Sign out</Button>
        </Card>
      </div>
    </div>
  );
}

function EtsyCheckCard() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; detail: string; status?: number } | null>(null);

  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.etsyCheck());
    } catch (err) {
      setResult({ ok: false, detail: err instanceof Error ? err.message : "Check failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Etsy connection</h3>
          <p className="text-sm text-muted-foreground">
            Tests your ETSY_API_KEY with a real Etsy API call and shows exactly what Etsy answers.
          </p>
        </div>
        <Button variant="outline" onClick={run} disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Test connection
        </Button>
      </div>
      {result && (
        <div className={`mt-4 rounded-lg border p-3 text-sm ${result.ok ? "border-green-600/40 bg-green-600/10 text-green-500" : "border-destructive/40 bg-destructive/10 text-destructive"}`}>
          {result.ok ? "✓ " : "✗ "}
          {result.detail}
        </div>
      )}
    </Card>
  );
}
