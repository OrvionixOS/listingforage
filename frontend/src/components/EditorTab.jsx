import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function EditorTab({ listingId, output, price }) {
  const ls = output.listing_strategy;
  const [title, setTitle] = useState(ls.titles[0].title);
  const [tags, setTags] = useState(ls.tags.join(", "));
  const [blocks, setBlocks] = useState(ls.description_blocks.map((b) => ({ ...b })));
  const [materials, setMaterials] = useState(output.product_analysis.materials_or_format.join(", "));
  const [priceVal, setPriceVal] = useState(price ?? "");
  const [scores, setScores] = useState(null);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [assistBusy, setAssistBusy] = useState("");
  const [assistNote, setAssistNote] = useState(null);

  useEffect(() => { api.quality(listingId).then(setScores).catch(() => {}); }, [listingId]);

  const save = async () => {
    setBusy(true); setErr(""); setSaved(false);
    try {
      const body = {
        title: title.trim(),
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        description_blocks: blocks.map((b) => ({ heading: b.heading, body: b.body,
                                                 bde_stage: b.bde_stage,
                                                 uncertainty_resolved: b.uncertainty_resolved })),
        materials: materials.split(",").map((m) => m.trim()).filter(Boolean),
      };
      if (priceVal !== "") body.price = Number(priceVal);
      const r = await api.editListing(listingId, body);
      setScores(r.scores);
      setSaved(true);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const runAssist = async (field, blockIndex) => {
    const key = field + (blockIndex ?? "");
    setAssistBusy(key); setErr(""); setAssistNote(null);
    try {
      const r = await api.assist(listingId, { field, block_index: blockIndex });
      if (field === "title") setTitle(r.improved_value);
      if (field === "tags") setTags(r.improved_value);
      if (field === "description_block") {
        setBlocks(blocks.map((b, i) => i === blockIndex ? { ...b, body: r.improved_value } : b));
      }
      setAssistNote({ field: key, rationale: r.rationale, addressed: r.uncertainty_addressed });
      setSaved(false);
    } catch (e) { setErr(e.message); } finally { setAssistBusy(""); }
  };

  const tagList = tags.split(",").map((t) => t.trim()).filter(Boolean);

  return (
    <>
      <QualityPanel scores={scores} />

      <div className="card">
        <h2>Title</h2>
        <textarea rows={2} value={title} onChange={(e) => { setTitle(e.target.value); setSaved(false); }}
                  aria-label="Listing title" style={{ width: "100%" }} />
        <div className="sub mono" style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
          <span style={{ color: title.length > 140 ? "var(--red)" : undefined }}>{title.length}/140</span>
          <button className="btn-ghost" disabled={!!assistBusy} onClick={() => runAssist("title")}>
            {assistBusy === "title" ? "Improving…" : "AI improve"}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Tags <span className="sub mono">({tagList.length}/13)</span></h2>
        <textarea rows={2} value={tags} onChange={(e) => { setTags(e.target.value); setSaved(false); }}
                  aria-label="Tags, comma separated" style={{ width: "100%" }} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
          {tagList.map((t, i) => (
            <span key={i} className={`pill ${t.length > 20 ? "red" : ""}`}>{t} <span className="sub mono">{t.length}</span></span>
          ))}
        </div>
        <button className="btn-ghost" style={{ marginTop: 10 }} disabled={!!assistBusy}
                onClick={() => runAssist("tags")}>
          {assistBusy === "tags" ? "Improving…" : "AI improve tag set"}
        </button>
      </div>

      <div className="card">
        <h2>Description</h2>
        {blocks.map((b, i) => (
          <div key={i} style={{ marginBottom: 18 }}>
            <input value={b.heading} aria-label={`Block ${i + 1} heading`}
                   onChange={(e) => { setBlocks(blocks.map((x, j) => j === i ? { ...x, heading: e.target.value } : x)); setSaved(false); }}
                   style={{ width: "100%", fontWeight: 600 }} />
            <textarea rows={3} value={b.body} aria-label={`Block ${i + 1} body`}
                      onChange={(e) => { setBlocks(blocks.map((x, j) => j === i ? { ...x, body: e.target.value } : x)); setSaved(false); }}
                      style={{ width: "100%", marginTop: 6 }} />
            <div className="sub mono" style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <span>stage: {b.bde_stage}{b.uncertainty_resolved != null && ` · resolves doubt #${b.uncertainty_resolved}`}</span>
              <button className="btn-ghost" disabled={!!assistBusy}
                      onClick={() => runAssist("description_block", i)}>
                {assistBusy === "description_block" + i ? "Improving…" : "AI improve"}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Materials &amp; price</h2>
        <label className="field"><span>Materials / format (comma separated)</span>
          <input value={materials} onChange={(e) => { setMaterials(e.target.value); setSaved(false); }} /></label>
        <label className="field" style={{ maxWidth: 200 }}><span>Price (USD)</span>
          <input type="number" min="0.20" step="0.01" value={priceVal}
                 onChange={(e) => { setPriceVal(e.target.value); setSaved(false); }} /></label>
      </div>

      {assistNote && (
        <div className="card" style={{ borderColor: "var(--gold)" }}>
          <h2>Why the AI changed it</h2>
          <p style={{ marginTop: 8 }}>{assistNote.rationale}</p>
          <p className="sub" style={{ marginTop: 6 }}>Addresses: {assistNote.addressed}</p>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 30 }}>
        <button className="btn" disabled={busy} onClick={save}>
          {busy ? "Saving + rescoring…" : "Save changes"}
        </button>
        {saved && <span className="pill green">saved — scores refreshed</span>}
        {err && <span className="error-text" style={{ margin: 0 }}>{err}</span>}
      </div>
    </>
  );
}

export function QualityPanel({ scores }) {
  if (!scores) return null;
  const core = ["conversion_score", "CTR_score", "trust_score", "clarity_score",
                "seo_score", "mobile_score", "listing_completeness_score"];
  const label = (k) => k.replace(/_score$/, "").replace(/_/g, " ").replace("CTR", "CTR");
  return (
    <div className="card">
      <h2>Live quality panel</h2>
      <div className="stat-row" style={{ marginTop: 12 }}>
        {core.map((k) => scores[k] && (
          <div className="stat" key={k}>
            <div className="stat-value">{scores[k].score}</div>
            <div className="stat-label">{label(k)}</div>
          </div>
        ))}
        {scores.brand_consistency && (
          <div className="stat">
            <div className="stat-value">{scores.brand_consistency.score ?? "—"}</div>
            <div className="stat-label">brand</div>
          </div>
        )}
        {scores.compliance && (
          <div className="stat">
            <div className="stat-value">{scores.compliance.score}</div>
            <div className="stat-label">compliance</div>
          </div>
        )}
      </div>
      {[scores.brand_consistency, scores.compliance].map((s, i) => s && s.problems?.length > 0 && (
        <div key={i} style={{ marginTop: 10 }}>
          {s.problems.slice(0, 3).map((p, j) => (
            <div className="u-item" key={j}><div className="sev sev-3">→</div><div className="sub">{p}</div></div>
          ))}
        </div>
      ))}
    </div>
  );
}
