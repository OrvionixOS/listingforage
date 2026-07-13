import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { fetchMe } from "@/lib/api";
import { DashboardShell } from "@/components/dashboard-shell";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: async () => {
    const user = await fetchMe();
    if (!user) throw redirect({ to: "/auth" });
    return { user };
  },
  component: () => (
    <DashboardShell>
      <Outlet />
    </DashboardShell>
  ),
});
