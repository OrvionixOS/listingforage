import { useEffect, useState } from "react";
import { api } from "../lib/api";

const STATE_PILL = { strong: "green", adequate: "gold", "at risk": "red" };

export default function JourneyTab({ listingId, genImages }) {
  const [j, setJ] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => { api.journey(listingId).then(setJ).catch((e) => setErr(e.message)); }, [listingId]);
  if (err) return <div className="error-text">{err}</div>;
  if (!j) return <p className="sub"><span className="spinner" />Simulating buyer journey…</p>;

  const thumb = j.search_result.thumbnail_slot != null
    ? genImages[j.search_result.thumbnail_slot]?.blobUrl : null;

  return (
    <>
      <div className="card">
        <h2>1 · Search results appearance</h2>
        <p className="sub">What a buyer sees before they ever click.</p>
        <div style={{ display: "flex", gap: 14, marginTop: 14, alignItems: "flex-start" }}>
          {thumb && <img src={thumb} alt="search thumbnail" loading="lazy"
                         style={{ width: 150, height: 150, objectFit: "cover", borderRadius: 8,
                                  border: "1px solid var(--hairline)" }} />}
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>{j.search_result.title_shown}</div>
            {j.search_result.price != null && (
              <div className="mono" style={{ color: "var(--gold)", marginTop: 4 }}>
                USD {Number(j.search_result.price).toFixed(2)}</div>
            )}
            <div className="sub mono" style={{ fontSize: 12, marginTop: 10 }}>
              mobile truncation: “{j.search_result.title_mobile}”
            </div>
            {j.search_result.thumbnail_score != null && (
              <div className="sub mono" style={{ fontSize: 12 }}>
                thumbnail pixel score: {j.search_result.thumbnail_score}/100
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h2>2 · Image sequence</h2>
        <p className="sub">The psychological order a buyer scrolls through.</p>
        {j.image_sequence.map((s) => (
          <div className="u-item" key={s.position}>
            <div className="sev sev-2" aria-hidden="true">{s.position}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>{s.purpose}</div>
              <div className="sub mono" style={{ fontSize: 12 }}>
                stage: {s.psychological_stage} · pixel {s.score}/100</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>3 · Reading flow</h2>
        <p className="sub">How the description walks the buyer through their doubts.</p>
        {j.reading_flow.map((b, i) => (
          <div className="u-item" key={i}>
            <div className="sev sev-2" aria-hidden="true">¶</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>{b.heading}</div>
              <div className="sub mono" style={{ fontSize: 12 }}>
                stage: {b.stage}{b.resolves != null && ` · resolves doubt #${b.resolves}`}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>4 · Decision timeline</h2>
        {j.decision_timeline.map((d) => (
          <div className="u-item" key={d.stage}>
            <div style={{ width: 150, textTransform: "capitalize" }}>{d.stage.replace(/_/g, " ")}</div>
            <div className="progress-track" style={{ flex: 1 }}>
              <div className="progress-fill" style={{ width: `${d.score}%` }} />
            </div>
            <div className="mono" style={{ width: 36, textAlign: "right" }}>{d.score}</div>
            <span className={`pill ${STATE_PILL[d.state] || ""}`}>{d.state}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>5 · Where buyers lose confidence</h2>
        {j.friction_points.length === 0 && (
          <p className="sub" style={{ marginTop: 8 }}>
            No high-friction points detected — every major doubt has an answer.</p>
        )}
        {j.friction_points.map((f, i) => (
          <div className="u-item" key={i}>
            <div className={`sev ${f.severity === "high" ? "sev-5" : "sev-3"}`} aria-hidden="true">!</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5, textTransform: "capitalize" }}>
                {f.where.replace(/_/g, " ")} <span className="sub">({f.severity})</span></div>
              <div className="sub" style={{ fontSize: 13 }}>{f.issue}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
