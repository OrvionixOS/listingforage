import { useEffect, useState } from "react";
import { api } from "../lib/api";

const STATUS_PILL = { complete: "green", generating: "gold", failed: "red",
                      queued: "gold", draft: "" };

export default function Dashboard({ onOpen, onNew }) {
  const [ov, setOv] = useState(null);
  const [err, setErr] = useState("");

  const load = () => api.overview().then(setOv).catch((e) => setErr(e.message));

  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  if (err) return <div className="error-text">{err}</div>;
  if (!ov) return <p className="sub"><span className="spinner" />Loading workspace…</p>;

  const { counts, performance, recent, recommendations, quota, plan } = ov;

  return (
    <>
      <h1>Workspace</h1>
      <p className="sub">Every listing is built from a Buyer Decision Engine analysis —
        six stages, one uncertainty map.</p>

      <div className="stat-row" role="group" aria-label="Listing counts">
        <Stat label="Listings" value={counts.total} />
        <Stat label="Generating" value={counts.generating} live={counts.generating > 0} />
        <Stat label="Drafts ready" value={counts.drafts} />
        <Stat label="Published" value={counts.published} />
        <Stat label="Views" value={performance.views} />
        <Stat label="Favorites" value={performance.favorites} />
        <Stat label="Fav. rate" value={performance.favorite_rate != null
          ? (performance.favorite_rate * 100).toFixed(1) + "%" : "—"} />
      </div>

      {recommendations.length > 0 && (
        <div className="card">
          <h2>Recommended next moves</h2>
          {recommendations.map((r, i) => (
            <div className="u-item" key={i}>
              <div className="sev sev-3" aria-hidden="true">→</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{r.title}</div>
                <div className="sub" style={{ fontSize: 13 }}>{r.action}</div>
              </div>
              {r.link && <button className="btn-ghost" onClick={() => onOpen(r.link)}>Open</button>}
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Recent projects</h2>
          <button className="btn" onClick={onNew}>New listing</button>
        </div>
        {recent.length === 0 && (
          <p className="sub" style={{ marginTop: 12 }}>
            No projects yet — create your first listing and the engine takes it from there.
          </p>
        )}
        {recent.map((l) => (
          <div className="listing-row" key={l.id}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis",
                            whiteSpace: "nowrap" }}>{l.title}</div>
              <div className="sub mono" style={{ fontSize: 12 }}>
                {new Date(l.updated_at).toLocaleDateString()}
                {l.category ? ` · ${l.category.replace("_", " ")}` : ""}
                {l.status === "generating" && l.progress && (
                  <> · step {l.progress.index}/{l.progress.total}: {l.progress.step.replace(/_/g, " ")}</>
                )}
              </div>
              {l.status === "generating" && l.progress && (
                <div className="progress-track" role="progressbar"
                     aria-valuenow={l.progress.index} aria-valuemin={0} aria-valuemax={l.progress.total}>
                  <div className="progress-fill"
                       style={{ width: `${(100 * l.progress.index) / l.progress.total}%` }} />
                </div>
              )}
            </div>
            <span className={`pill ${STATUS_PILL[l.status] || ""}`}>{l.status}</span>
            <button className="btn-ghost" onClick={() => onOpen(l.id)}
                    aria-label={`Open ${l.title}`}>
              {l.status === "generating" ? "Resume" : "Open"}
            </button>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Plan &amp; usage</h2>
        <p className="sub" style={{ marginTop: 8 }}>
          <span className="pill gold">{plan}</span>{" "}
          {quota.limit
            ? `${quota.used} of ${quota.limit} generations used this cycle · ${quota.remaining} left`
            : "unlimited generations"}
        </p>
        {quota.limit > 0 && (
          <div className="progress-track" style={{ marginTop: 10 }}>
            <div className="progress-fill" style={{ width: `${(100 * quota.used) / quota.limit}%` }} />
          </div>
        )}
      </div>
    </>
  );
}

function Stat({ label, value, live }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}{live && <span className="spinner" style={{ marginLeft: 6 }} />}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
