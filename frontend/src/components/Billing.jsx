import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Billing({ user }) {
  const [plans, setPlans] = useState(null);
  const [quota, setQuota] = useState(user?.quota || null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.plans().then(setPlans);
    api.quota().then(setQuota);
  }, []);

  const upgrade = async (plan) => {
    setError("");
    try {
      const { checkout_url } = await api.checkout(plan);
      window.location.href = checkout_url;
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div>
      <h1>Plan &amp; usage</h1>
      {quota && (
        <div className="card">
          <h2>This month</h2>
          <p style={{ marginTop: 8 }}>
            <span className="mono" style={{ fontSize: 26, color: "var(--gold-bright)" }}>
              {quota.used} / {quota.limit}
            </span>{" "}
            <span className="sub">listings generated on the {quota.plan} plan</span>
          </p>
          <div className="rail-meter" style={{ marginTop: 12, maxWidth: 420 }}>
            <div style={{ width: `${Math.min((quota.used / quota.limit) * 100, 100)}%` }} />
          </div>
        </div>
      )}
      {plans && (
        <div className="card">
          <h2>Plans</h2>
          {Object.entries(plans).map(([name, p]) => (
            <div className="row-item" key={name}>
              <div>
                <div className="row-title" style={{ textTransform: "capitalize" }}>{name}</div>
                <div className="sub">{p.listings_per_month.toLocaleString()} listings / month</div>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className="mono">${p.price_usd}/mo</span>
                {name !== "free" && quota?.plan !== name && (
                  <button className="btn-ghost" onClick={() => upgrade(name)}>Upgrade</button>
                )}
                {quota?.plan === name && <span className="pill gold">current</span>}
              </div>
            </div>
          ))}
          {error && <div className="error-text">{error}</div>}
        </div>
      )}
    </div>
  );
}
