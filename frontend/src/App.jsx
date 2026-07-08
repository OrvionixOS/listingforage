import { useEffect, useState } from "react";
import { api, clearToken, getToken } from "./lib/api";
import Auth from "./components/Auth";
import Dashboard from "./components/Dashboard";
import NewListing from "./components/NewListing";
import ListingDetail from "./components/ListingDetail";
import Billing from "./components/Billing";
import BrandStudio from "./components/BrandStudio";
import BulkOps from "./components/BulkOps";
import Notifications from "./components/Notifications";

export default function App() {
  const [user, setUser] = useState(null);
  const [booted, setBooted] = useState(false);
  const [view, setView] = useState({ name: "dashboard" });

  const loadUser = () =>
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setBooted(true));

  useEffect(() => {
    if (getToken()) loadUser(); else setBooted(true);
    const onLogout = () => setUser(null);
    window.addEventListener("lf:logout", onLogout);
    return () => window.removeEventListener("lf:logout", onLogout);
  }, []);

  if (!booted) return null;
  if (!user) return <Auth onAuthed={loadUser} />;

  const nav = (name, extra = {}) => setView({ name, ...extra });

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="wordmark">Listing<em>Forge</em></div>
        <div className="tagline">Conversion Intelligence</div>
        <button className={`nav-item ${view.name === "dashboard" ? "active" : ""}`}
          onClick={() => nav("dashboard")}>Listings</button>
        <button className={`nav-item ${view.name === "new" ? "active" : ""}`}
          onClick={() => nav("new")}>New listing</button>
        <button className={`nav-item ${view.name === "bulk" ? "active" : ""}`}
          onClick={() => nav("bulk")}>Bulk generate</button>
        <button className={`nav-item ${view.name === "brand" ? "active" : ""}`}
          onClick={() => nav("brand")}>Brand studio</button>
        <button className={`nav-item ${view.name === "billing" ? "active" : ""}`}
          onClick={() => nav("billing")}>Plan &amp; usage</button>
        <Notifications onOpen={(id) => nav("detail", { id })} />
        <div className="sidebar-footer">
          <div>{user.email}</div>
          <button className="nav-item" style={{ paddingLeft: 0 }}
            onClick={() => { clearToken(); setUser(null); }}>Sign out</button>
        </div>
      </aside>
      <main className="main">
        {view.name === "dashboard" && (
          <Dashboard onOpen={(id) => nav("detail", { id })} onNew={() => nav("new")} />
        )}
        {view.name === "new" && (
          <NewListing user={user} onCreated={(id) => nav("detail", { id })} />
        )}
        {view.name === "detail" && (
          <ListingDetail id={view.id} onBack={() => nav("dashboard")} />
        )}
        {view.name === "billing" && <Billing user={user} />}
        {view.name === "brand" && <BrandStudio />}
        {view.name === "bulk" && <BulkOps onOpen={(id) => nav("detail", { id })} />}
      </main>
    </div>
  );
}
