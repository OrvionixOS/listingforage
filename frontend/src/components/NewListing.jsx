import { useRef, useState } from "react";
import { api } from "../lib/api";

/*
 * Photos-first intake wizard.
 *  1. Drop product photos           -> instant pixel analysis
 *  2. Answer only what pixels can't -> product, type, price
 *  3. Brand branch                  -> use existing brand / quick-create / none
 *  4. Generate                      -> 11-step pipeline takes over
 */
export default function NewListing({ onCreated }) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // step 1: photos
  const [files, setFiles] = useState([]);          // {id, name, previewUrl}
  const [analysis, setAnalysis] = useState(null);
  const fileInput = useRef(null);

  // step 2: product questions
  const [what, setWhat] = useState("");
  const [kind, setKind] = useState("digital");     // digital | physical (digital-first)
  const [price, setPrice] = useState("");
  const [extra, setExtra] = useState("");

  // step 3: brand branch
  const [useBrand, setUseBrand] = useState(true);
  const [hasBrand, setHasBrand] = useState(null);  // null until answered
  const [bName, setBName] = useState("");
  const [bVoice, setBVoice] = useState("");
  const [bPillars, setBPillars] = useState("");

  const addFiles = async (list) => {
    setErr(""); setBusy(true);
    try {
      const added = [];
      for (const f of Array.from(list)) {
        const r = await api.upload(f);
        added.push({ id: r.upload_id, name: f.name,
                     previewUrl: URL.createObjectURL(f) });
      }
      setFiles((p) => [...p, ...added]);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const analyze = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.intakeAnalyze(files.map((f) => f.id));
      setAnalysis(r);
      if (r.suggested.category_guess && !what) setWhat(r.suggested.category_guess);
      setStep(2);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const toBrandStep = () => {
    if (!what.trim() || !kind) { setErr("Tell me what it is and pick a type."); return; }
    setErr(""); setStep(3);
  };

  const generate = async () => {
    setBusy(true); setErr("");
    try {
      // quick brand creation if they answered "yes, but not set up here"
      if (!analysis.brand_configured && hasBrand && bName.trim()) {
        await api.saveBrand({
          brand_name: bName.trim(), voice: bVoice.trim(),
          messaging_pillars: bPillars.split(",").map((s) => s.trim()).filter(Boolean),
          photography_style: "", packaging_guidelines: "", palette:
            (analysis.suggested.palette || []).slice(0, 3).join(", "),
          apply_to_generations: true,
        });
      }
      if (analysis.brand_configured && !useBrand) {
        const b = await api.brand();
        await api.saveBrand({ ...b, apply_to_generations: false });
      }
      const description = [
        `${what.trim()} — ${kind} product.`,
        analysis.suggested.materials_guess?.length
          ? `Materials/format: ${analysis.suggested.materials_guess.join(", ")}.` : "",
        extra.trim(),
      ].filter(Boolean).join(" ");
      const r = await api.generate({
        title: what.trim().slice(0, 140),
        description,
        price: price ? Number(price) : undefined,
        notes: extra.trim() || undefined,
        image_ids: files.map((f) => f.id),
      });
      onCreated(r.listing_id);
    } catch (e) { setErr(e.message); setBusy(false); }
  };

  return (
    <>
      <h1>New listing</h1>
      <p className="sub">Drop photos. Answer a few questions. The engine does the rest.</p>

      <div className="wizard-steps" aria-label="Progress">
        {["Photos", "Product", "Brand", "Generate"].map((label, i) => (
          <span key={label} className={`wizard-step ${step > i ? "done" : ""} ${step === i + 1 ? "current" : ""}`}>
            {i + 1}. {label}
          </span>
        ))}
      </div>

      {err && <div className="error-text">{err}</div>}

      {step === 1 && (
        <div className="card">
          <h2>Product files</h2>
          <p className="sub">For digital products, these ARE the product — upload the
            actual textures, papers, or assets buyers will download. No limit.
            I'll read palette and quality from a sample, and the 7-image Etsy
            gallery gets generated separately from this analysis.</p>
          <div className="dropzone" role="button" tabIndex={0}
               onClick={() => fileInput.current?.click()}
               onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
               onDragOver={(e) => e.preventDefault()}
               onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}>
            {files.length === 0
              ? <span>Tap to choose your product files, or drag them here</span>
              : <span>{files.length} file(s) added — tap to add more</span>}
          </div>
          <input ref={fileInput} type="file" accept="image/*,.pdf,.zip" multiple hidden
                 onChange={(e) => addFiles(e.target.files)} />
          {files.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12,
                          alignItems: "center" }}>
              {files.slice(0, 12).map((f) => (
                <img key={f.id} src={f.previewUrl} alt={f.name}
                     style={{ width: 72, height: 72, objectFit: "cover",
                              borderRadius: 8, border: "1px solid var(--hairline)" }} />
              ))}
              {files.length > 12 && (
                <span className="sub mono">+{files.length - 12} more</span>
              )}
            </div>
          )}
          <button className="btn" style={{ marginTop: 16 }}
                  disabled={busy || files.length === 0} onClick={analyze}>
            {busy ? "Reading your photos…" : "Analyze photos →"}
          </button>
        </div>
      )}

      {step === 2 && analysis && (
        <div className="card">
          <h2>About the product</h2>
          {analysis.photo_warnings.length > 0 && (
            <div style={{ margin: "10px 0" }}>
              {analysis.photo_warnings.map((w, i) => (
                <div className="u-item" key={i}>
                  <div className="sev sev-3" aria-hidden="true">!</div>
                  <div className="sub">{w} — the image strategy will compensate.</div>
                </div>
              ))}
            </div>
          )}
          {analysis.suggested.palette?.length > 0 && (
            <p className="sub" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              Detected palette:
              {analysis.suggested.palette.slice(0, 4).map((c) => (
                <span key={c} title={c} style={{ width: 16, height: 16, borderRadius: 4,
                  background: c, display: "inline-block",
                  border: "1px solid var(--hairline)" }} />
              ))}
            </p>
          )}
          <label className="field"><span>What is this product? (one line)</span>
            <input value={what} onChange={(e) => setWhat(e.target.value)}
                   placeholder="e.g. Liquid gold foil digital paper pack, 12 seamless textures" /></label>
          <div className="field"><span>Type</span>
            <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
              {["digital", "physical"].map((k) => (
                <button key={k} className={kind === k ? "btn" : "btn-ghost"}
                        onClick={() => setKind(k)} aria-pressed={kind === k}>
                  {k === "digital" ? "Digital download" : "Physical item"}
                </button>
              ))}
            </div>
          </div>
          <label className="field" style={{ maxWidth: 200 }}><span>Price (USD)</span>
            <input type="number" min="0.20" step="0.01" value={price}
                   onChange={(e) => setPrice(e.target.value)} placeholder="8.99" /></label>
          <label className="field"><span>Anything buyers must know? (optional)</span>
            <input value={extra} onChange={(e) => setExtra(e.target.value)}
                   placeholder="e.g. 300 DPI, commercial license included" /></label>
          <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
            <button className="btn-ghost" onClick={() => setStep(1)}>← Back</button>
            <button className="btn" onClick={toBrandStep}>Continue →</button>
          </div>
        </div>
      )}

      {step === 3 && analysis && (
        <div className="card">
          <h2>Brand</h2>
          {analysis.brand_configured ? (
            <>
              <p className="sub">You have a brand system set up
                {analysis.brand_name ? <> — <strong>{analysis.brand_name}</strong></> : ""}.</p>
              <label style={{ display: "flex", gap: 10, alignItems: "center",
                              cursor: "pointer", marginTop: 12 }}>
                <input type="checkbox" checked={useBrand}
                       onChange={(e) => setUseBrand(e.target.checked)} />
                <span>Apply it to this listing's copy and image direction</span>
              </label>
            </>
          ) : hasBrand === null ? (
            <>
              <p className="sub">Do you have an established brand for this shop?</p>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="btn" onClick={() => setHasBrand(true)}>Yes</button>
                <button className="btn-ghost" onClick={() => setHasBrand(false)}>
                  No — just make it convert</button>
              </div>
            </>
          ) : hasBrand ? (
            <>
              <p className="sub">Three quick questions — this becomes your Brand Studio
                profile and applies to every future listing.</p>
              <label className="field"><span>Brand name</span>
                <input value={bName} onChange={(e) => setBName(e.target.value)}
                       placeholder="Digital Glow Press" /></label>
              <label className="field"><span>Voice, in a few words</span>
                <input value={bVoice} onChange={(e) => setBVoice(e.target.value)}
                       placeholder="luxury, editorial, precise, warm" /></label>
              <label className="field"><span>2-3 things every listing should say (comma separated)</span>
                <input value={bPillars} onChange={(e) => setBPillars(e.target.value)}
                       placeholder="seamless textures, instant download, 300 DPI quality" /></label>
              <p className="sub" style={{ fontSize: 12.5 }}>
                Palette will start from your photos' detected colors — refine later in Brand studio.</p>
            </>
          ) : (
            <p className="sub" style={{ marginTop: 8 }}>No problem — the listing will be
              built purely for conversion. You can add a brand system any time.</p>
          )}
          <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
            <button className="btn-ghost" onClick={() => { setStep(2); setHasBrand(null); }}>← Back</button>
            <button className="btn" disabled={busy || (!analysis.brand_configured && hasBrand && !bName.trim())}
                    onClick={generate}>
              {busy ? "Starting the engine…" : "Generate listing →"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
