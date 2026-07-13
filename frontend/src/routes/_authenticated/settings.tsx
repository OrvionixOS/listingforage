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
