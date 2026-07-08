import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function BrandStudio() {
  const [b, setB] = useState(null);
  const [pillar, setPillar] = useState("");
  const [saved, setSaved] = useState(false);
  const [preview, setPreview] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { api.brand().then(setB).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="error-text">{err}</div>;
  if (!b) return <p className="sub"><span className="spinner" />Loading brand profile…</p>;

  const set = (k, v) => { setB({ ...b, [k]: v }); setSaved(false); };

  const save = async () => {
    setErr("");
    try {
      const r = await api.saveBrand(b);
      setSaved(true);
      setPreview(r.context_preview || "");
    } catch (e) { setErr(e.message); }
  };

  const addPillar = () => {
    const p = pillar.trim();
    if (p && b.messaging_pillars.length < 12) {
      set("messaging_pillars", [...b.messaging_pillars, p]);
      setPillar("");
    }
  };

  return (
    <>
      <h1>Brand studio</h1>
      <p className="sub">One brand system, applied to every generation — copy voice,
        image direction, and a consistency score on each listing.</p>

      <div className="card">
        <h2>Identity</h2>
        <label className="field"><span>Brand name</span>
          <input value={b.brand_name} onChange={(e) => set("brand_name", e.target.value)}
                 placeholder="Digital Glow Press" /></label>
        <label className="field"><span>Voice</span>
          <textarea rows={2} value={b.voice} onChange={(e) => set("voice", e.target.value)}
                    placeholder="luxury, editorial, precise, warm" /></label>
        <label className="field"><span>Palette</span>
          <input value={b.palette} onChange={(e) => set("palette", e.target.value)}
                 placeholder="obsidian, ivory, antique gold" /></label>
      </div>

      <div className="card">
        <h2>Messaging pillars</h2>
        <p className="sub">The claims every listing should reinforce. The consistency
          checker verifies each one appears in the copy.</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0" }}>
          {b.messaging_pillars.map((p, i) => (
            <span key={i} className="pill gold">
              {p}{" "}
              <button aria-label={`Remove pillar ${p}`} className="pill-x"
                onClick={() => set("messaging_pillars", b.messaging_pillars.filter((_, j) => j !== i))}>
                ×</button>
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={pillar} onChange={(e) => setPillar(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && addPillar()}
                 placeholder="e.g. seamless print-ready textures" style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={addPillar}>Add</button>
        </div>
      </div>

      <div className="card">
        <h2>Visual direction</h2>
        <label className="field"><span>Photography style</span>
          <textarea rows={2} value={b.photography_style}
                    onChange={(e) => set("photography_style", e.target.value)}
                    placeholder="macro luxury, softbox lighting, specular highlights" /></label>
        <label className="field"><span>Packaging guidelines</span>
          <textarea rows={2} value={b.packaging_guidelines}
                    onChange={(e) => set("packaging_guidelines", e.target.value)}
                    placeholder="minimal matte black, gold foil wordmark" /></label>
      </div>

      <div className="card">
        <label style={{ display: "flex", gap: 10, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={b.apply_to_generations}
                 onChange={(e) => set("apply_to_generations", e.target.checked)} />
          <span>Apply this brand system to all new generations</span>
        </label>
        <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn" onClick={save}>Save brand profile</button>
          {saved && <span className="pill green">saved</span>}
        </div>
        {preview && (
          <pre className="mono" style={{ marginTop: 14, fontSize: 12, whiteSpace: "pre-wrap",
                                          color: "var(--ink-dim)" }}>{preview}</pre>
        )}
        {err && <div className="error-text">{err}</div>}
      </div>
    </>
  );
}
