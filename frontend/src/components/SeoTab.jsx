import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function SeoTab({ listingId }) {
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => { api.seo(listingId).then(setR).catch((e) => setErr(e.message)); }, [listingId]);
  if (err) return <div className="error-text">{err}</div>;
  if (!r) return <p className="sub"><span className="spinner" />Analyzing SEO…</p>;

  return (
    <>
      <div className="card">
        <h2>Search intent</h2>
        <p className="sub" style={{ marginTop: 8 }}>
          Primary keyword: <span className="pill gold">{r.primary_keyword}</span>
        </p>
        <p className="sub" style={{ marginTop: 8 }}>
          Buyer: {r.search_intent.buyer}<br />Occasion: {r.search_intent.occasion}
        </p>
      </div>

      <div className="card">
        <h2>Title optimization <span className="pill gold">{r.title.score}/100</span></h2>
        <p className="mono" style={{ marginTop: 10, fontSize: 13 }}>{r.title.text}</p>
        <div style={{ marginTop: 12 }}>
          {Object.entries(r.title.checks).map(([check, ok]) => (
            <div className="u-item" key={check}>
              <div className={`sev ${ok ? "sev-1" : "sev-5"}`} aria-hidden="true">{ok ? "✓" : "✗"}</div>
              <div className="sub">{check}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Tag strength <span className="pill gold">avg {r.tag_average_strength}/100</span></h2>
        {r.tags.map((t) => (
          <div className="u-item" key={t.tag}>
            <div style={{ width: 170 }} className="mono">{t.tag}</div>
            <div className="progress-track" style={{ flex: 1 }}>
              <div className="progress-fill" style={{ width: `${t.strength}%` }} />
            </div>
            <div className="mono" style={{ width: 34, textAlign: "right" }}>{t.strength}</div>
            {t.notes.length > 0 && (
              <div className="sub" style={{ fontSize: 11.5, width: 220 }}>{t.notes.join(" · ")}</div>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Keyword suggestions</h2>
        {r.suggestions.length === 0 && (
          <p className="sub" style={{ marginTop: 8 }}>Full coverage — the strategy's
            keywords all made it into the tags.</p>
        )}
        {r.suggestions.map((s, i) => (
          <div className="u-item" key={i}>
            <div className="sev sev-3" aria-hidden="true">+</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }} className="mono">{s.suggestion}</div>
              <div className="sub" style={{ fontSize: 12.5 }}>{s.why}
                <span className="mono"> — {s.source}</span></div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
