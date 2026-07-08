import { useEffect, useState } from "react";
import { api } from "../lib/api";
import EditorTab from "./EditorTab";
import JourneyTab from "./JourneyTab";
import SeoTab from "./SeoTab";
import StudioPanel from "./StudioPanel";

const STAGE_ORDER = ["attention", "interpretation", "trust", "usage_imagination", "value_justification", "final_objection"];
const STAGE_LABEL = {
  attention: "Attention", interpretation: "Interpretation", trust: "Trust",
  usage_imagination: "Usage imagination", value_justification: "Value justification",
  final_objection: "Final objection",
};
const STAGE_SCORE_KEY = {
  attention: "attention_score", interpretation: "interpretation_score", trust: "trust_score",
  usage_imagination: "usage_imagination_score", value_justification: "value_justification_score",
  final_objection: "objection_score",
};
const SCORE_LABEL = {
  CTR_score: "CTR", trust_score: "Trust", clarity_score: "Clarity",
  conversion_score: "Conversion", seo_score: "SEO", mobile_score: "Mobile",
  listing_completeness_score: "Completeness",
};

function copy(text) { navigator.clipboard?.writeText(text); }

function renderPrompt(p) {
  if (!p) return "";
  const lines = [
    `SUBJECT: ${p.subject}`, `LIGHTING: ${p.lighting}`, `CAMERA: ${p.camera}`,
    `ENVIRONMENT: ${p.environment}`, `COMPOSITION: ${p.composition}`,
    `PRODUCT FOCUS: ${p.product_focus}`, `REALISM: ${p.realism_constraint}`,
  ];
  if (p.text_overlays?.length) lines.push(`TEXT OVERLAYS: ${p.text_overlays.map((t) => `"${t}"`).join(" ")}`);
  if (p.negative) lines.push(`NEGATIVE: ${p.negative}`);
  lines.push("Etsy conversion optimized, designed to reduce buyer uncertainty.");
  return lines.join("\n");
}

function scoreColor(v) {
  if (v >= 75) return "var(--signal-green)";
  if (v >= 50) return "var(--gold-bright)";
  return "var(--signal-red)";
}

export default function ListingDetail({ id, onBack }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("scores");
  const [exported, setExported] = useState("");
  const [openScore, setOpenScore] = useState(null);
  const [genImages, setGenImages] = useState({});   // slot_id -> {meta, blobUrl}
  const [regenBusy, setRegenBusy] = useState(null);

  const loadImages = async () => {
    try {
      const metas = await api.images(id);
      const next = {};
      for (const m of metas) {
        next[m.slot_id] = { meta: m, blobUrl: await api.imageBlob(id, m.slot_id) };
      }
      setGenImages(next);
    } catch { /* images may not exist yet */ }
  };

  const regenerate = async (slot) => {
    setRegenBusy(slot);
    try {
      await api.regenerateImage(id, slot);
      await loadImages();
    } finally {
      setRegenBusy(null);
    }
  };

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const d = await api.listing(id).catch(() => null);
      if (!alive) return;
      setData(d);
      if (d && d.status === "generating") setTimeout(load, 4000);
      if (d && d.status === "complete") loadImages();
    };
    load();
    return () => { alive = false; };
  }, [id]);

  if (!data) return <p className="sub"><span className="spinner" />Loading…</p>;

  if (data.status === "generating") return (
    <div>
      <button className="btn-ghost" onClick={onBack}>← Back</button>
      <h1 style={{ marginTop: 16 }}>{data.title}</h1>
      <div className="card">
        <p><span className="spinner" />
          Running the 11-step pipeline — analysis, Buyer Decision Engine, strategy,
          copy, image strategy, image generation, validation, sequencing.</p>
        {data.progress && (
          <>
            <div className="progress-track" style={{ marginTop: 16 }} role="progressbar"
                 aria-valuenow={data.progress.index} aria-valuemin={0}
                 aria-valuemax={data.progress.total}>
              <div className="progress-fill"
                   style={{ width: `${(100 * data.progress.index) / data.progress.total}%` }} />
            </div>
            <p className="sub mono" style={{ marginTop: 8 }}>
              step {data.progress.index}/{data.progress.total}: {data.progress.step.replace(/_/g, " ")}
            </p>
          </>
        )}
      </div>
    </div>
  );

  if (data.status === "failed") return (
    <div>
      <button className="btn-ghost" onClick={onBack}>← Back</button>
      <h1 style={{ marginTop: 16 }}>{data.title}</h1>
      <div className="card">
        <p className="error-text">Generation failed safe: {data.error}</p>
        <p className="sub" style={{ marginTop: 8 }}>No partial listing was saved and your quota was not charged.</p>
      </div>
    </div>
  );

  const out = data.output || {};
  const bde = out.buyer_decision_engine || {};
  const listing = out.listing_strategy || {};
  const slots = (out.image_prompts?.slots || []).slice().sort((a, b) => a.slot_id - b.slot_id);
  const report = out.validation_report || {};
  const scores = out.conversion_scores || {};
  const stageMap = Object.fromEntries((bde.stage_assessments || []).map((s) => [s.stage, s]));
  const uMap = Object.fromEntries((bde.buyer_uncertainty_map || []).map((u) => [u.id, u]));

  const doExport = async (fmt) => setExported(await api.exportFmt(id, fmt));

  return (
    <div>
      <button className="btn-ghost" onClick={onBack}>← Back</button>
      <h1 style={{ marginTop: 16 }}>{data.title}</h1>
      <p className="sub">
        <span className="pill gold">{(out.product_category || "").replace(/_/g, " ")}</span>
        {" "}<span className="pill">{Math.round((out.confidence || 0) * 100)}% confidence</span>
        {" "}<span className={`pill ${report.valid ? "green" : "red"}`}>
          {report.valid ? `validated · ${report.attempts} attempt${report.attempts > 1 ? "s" : ""}` : "validation failed"}
        </span>
      </p>
      <p className="sub" style={{ marginTop: 6 }}>Optimized for: {bde.dominant_purchase_scenario}</p>
      {out.classification?.fallback_reasoning && (
        <p className="sub mono" style={{ marginTop: 6 }}>fallback: {out.classification.fallback_reasoning}</p>
      )}

      <div className="tabs">
        {[["scores", "Quality"], ["editor", "Editor"], ["decision", "Decision map"], ["copy", "Titles & copy"], ["images", "Image studio"], ["journey", "Buyer journey"], ["seo", "SEO"], ["publish", "Publish"], ["export", "Export"]].map(([k, label]) => (
          <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>

      {tab === "scores" && (
        <>
          <div className="card">
            <h2>Conversion scorecard</h2>
            <p className="sub">Deterministic, auditable scores. Tap any score to see every contributing factor.</p>
            <div className="slot-grid" style={{ marginTop: 14 }}>
              {Object.entries(SCORE_LABEL).map(([key, label]) => {
                const cs = scores[key];
                if (!cs) return null;
                const open = openScore === key;
                return (
                  <div className="slot-card" key={key} style={{ cursor: "pointer" }}
                       onClick={() => setOpenScore(open ? null : key)}>
                    <div className="slot-head">
                      <span style={{ fontWeight: 700 }}>{label}</span>
                      <span className="slot-num" style={{ color: scoreColor(cs.score) }}>{cs.score}</span>
                    </div>
                    <div className="rail-meter"><div style={{ width: `${cs.score}%` }} /></div>
                    <p className="sub" style={{ marginTop: 10, fontSize: 13 }}>{cs.explanation}</p>
                    {open && (
                      <div style={{ marginTop: 10 }}>
                        {cs.contributing_factors.map((f, i) => (
                          <div key={i} className="u-item" style={{ padding: "8px 0" }}>
                            <div className={`sev ${f.impact >= 0 ? "sev-3" : "sev-5"}`}
                                 style={f.impact >= 0 ? { background: "rgba(127,174,139,.15)", color: "var(--signal-green)" } : {}}>
                              {f.impact >= 0 ? `+${f.impact}` : f.impact}
                            </div>
                            <div>
                              <div style={{ fontSize: 13.5 }}>{f.factor}</div>
                              <div className="sub" style={{ fontSize: 12.5 }}>{f.detail}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="card">
            <h2>Validation report</h2>
            <p className="sub">Image Strategy Validator — {report.attempts} generation attempt{report.attempts > 1 ? "s" : ""} to pass all checks.</p>
            {(report.checks || []).map((c, i) => (
              <div className="u-item" key={i}>
                <div className={`sev ${c.passed ? "" : "sev-5"}`}
                     style={c.passed ? { background: "rgba(127,174,139,.15)", color: "var(--signal-green)" } : {}}>
                  {c.passed ? "✓" : "✗"}
                </div>
                <div>
                  <div style={{ fontSize: 13.5 }}>{c.check.replace(/_/g, " ")}</div>
                  <div className="sub" style={{ fontSize: 12.5 }}>{c.detail}</div>
                </div>
              </div>
            ))}
            {(report.regeneration_feedback || []).length > 0 && (
              <>
                <h2 style={{ marginTop: 18 }}>Auto-regeneration history</h2>
                {report.regeneration_feedback.map((fb, i) => (
                  <p className="sub mono" key={i} style={{ marginTop: 6 }}>· {fb}</p>
                ))}
              </>
            )}
          </div>
        </>
      )}

      {tab === "decision" && (
        <>
          <div className="card">
            <h2>The buyer's path — six stage scores</h2>
            <p className="sub" style={{ marginBottom: 18 }}>Blend of measured input signals and buyer-model assessment. Low scores are where buyers leave.</p>
            <div className="rail">
              {STAGE_ORDER.map((stage, i) => {
                const s = stageMap[stage];
                const score = bde.scores?.[STAGE_SCORE_KEY[stage]] ?? 0;
                if (!s) return null;
                return (
                  <div className="rail-stage" key={stage}>
                    <div className="rail-dot">{i + 1}</div>
                    <div>
                      <div className="rail-name">{STAGE_LABEL[stage]} <span className="mono" style={{ color: scoreColor(score) }}>{score}</span></div>
                      <div className="rail-q">“{s.buyer_question}”</div>
                      <div className="rail-meter"><div style={{ width: `${score}%` }} /></div>
                      <div className="rail-meta">{(s.risks || [])[0] || ""}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <h2>Buyer uncertainty map</h2>
            <p className="sub">Every doubt in a buyer's head, ranked. Severity 4–5 blocks purchases.</p>
            <div style={{ marginTop: 10 }}>
              {(bde.buyer_uncertainty_map || []).slice().sort((a, b) => b.severity - a.severity).map((u) => (
                <div className="u-item" key={u.id}>
                  <div className={`sev sev-${u.severity}`}>{u.severity}</div>
                  <div>
                    <div>{u.uncertainty}</div>
                    <div className="sub mono">{STAGE_LABEL[u.stage] || u.stage} · resolve via {(u.resolvable_by || []).join(", ")}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>Trust gap analysis</h2>
            {(bde.trust_gap_analysis || []).map((g, i) => (
              <div className="u-item" key={i}>
                <div className={`sev sev-${g.severity}`}>{g.severity}</div>
                <div>
                  <div>{g.gap}</div>
                  <div className="sub" style={{ fontSize: 12.5 }}>Evidence: {g.evidence}</div>
                  <div className="sub mono" style={{ fontSize: 12 }}>remedy → {g.remedy}</div>
                </div>
              </div>
            ))}
            <h2 style={{ marginTop: 22 }}>Conversion blockers</h2>
            {(bde.conversion_blockers || []).map((b, i) => (
              <div className="u-item" key={i}><div className="sev sev-5">!</div><div>{b}</div></div>
            ))}
            <h2 style={{ marginTop: 22 }}>Emotional drivers</h2>
            <p className="sub">{(bde.emotional_drivers || []).join(" · ")}</p>
          </div>
        </>
      )}

      {tab === "copy" && (
        <>
          <div className="card">
            <h2>Title variants</h2>
            <p className="sub">Each exploits a different Buyer Decision Engine insight. Tap to copy.</p>
            {(listing.titles || []).map((t, i) => (
              <div className="row-item" key={i}>
                <div>
                  <div className="row-title">{t.title}</div>
                  <div className="sub">{t.strategy}</div>
                </div>
                <button className="btn-ghost" onClick={() => copy(t.title)}>Copy</button>
              </div>
            ))}
          </div>
          <div className="card">
            <h2>13 tags</h2>
            <div style={{ marginTop: 10 }}>{(listing.tags || []).map((t, i) => <span className="tag-chip" key={i}>{t}</span>)}</div>
            <button className="btn-ghost" style={{ marginTop: 12 }} onClick={() => copy((listing.tags || []).join(", "))}>Copy all tags</button>
          </div>
          <div className="card">
            <h2>Description architecture</h2>
            <p className="sub">Ordered to the buyer's decision sequence. Each block names the doubt it removes.</p>
            {(listing.description_blocks || []).map((b, i) => (
              <div key={i} style={{ marginTop: 18 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <strong>{b.heading}</strong>
                  <span className="pill">{STAGE_LABEL[b.bde_stage] || b.bde_stage}</span>
                </div>
                <p style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{b.body}</p>
                <p className="sub mono" style={{ marginTop: 4 }}>removes: {b.uncertainty_resolved}</p>
              </div>
            ))}
            {(listing.faq_items || []).length > 0 && <>
              <h2 style={{ marginTop: 24 }}>FAQ — final objection killers</h2>
              {listing.faq_items.map((f, i) => (
                <div key={i} style={{ marginTop: 12 }}>
                  <strong>{f.question}</strong>
                  <p>{f.answer}</p>
                </div>
              ))}
            </>}
          </div>
        </>
      )}

      {tab === "images" && (<>
        <StudioPanel listingId={id} slots={out.image_prompts.slots}
                     genImages={genImages} reload={loadImages} />
      </>)}
      {false && (
        <div className="card">
          <h2>The 7-image system</h2>
          <p className="sub">Each slot claims a different buyer uncertainty. Prompts carry mandatory lighting, camera, environment, composition, product-focus, and realism specs.</p>
          <div className="slot-grid">
            {slots.map((s) => (
              <div className="slot-card" key={s.slot_id}>
                <div className="slot-head">
                  <span className="slot-num">{s.slot_id}</span>
                  <span>
                    <span className="pill gold">{s.intent}</span>{" "}
                    <span className="pill">{STAGE_LABEL[s.psychological_stage] || s.psychological_stage}</span>
                  </span>
                </div>
                <div className="sub mono" style={{ fontSize: 11.5 }}>{s.required_visual_type}</div>
                {genImages[s.slot_id] && (
                  <div style={{ margin: "10px 0" }}>
                    <img src={genImages[s.slot_id].blobUrl} alt={`slot ${s.slot_id}`}
                         style={{ width: "100%", borderRadius: 8, border: "1px solid var(--hairline)" }} />
                    <div className="sub mono" style={{ fontSize: 11.5, marginTop: 6, display: "flex", justifyContent: "space-between" }}>
                      <span>pixel score {genImages[s.slot_id].meta.validation_score}/100
                        {genImages[s.slot_id].meta.regeneration_count > 0 &&
                          ` · ${genImages[s.slot_id].meta.regeneration_count} regen`}</span>
                      <span>seq #{genImages[s.slot_id].meta.display_order}</span>
                    </div>
                    <button className="btn-ghost" style={{ marginTop: 8 }}
                            disabled={regenBusy === s.slot_id}
                            onClick={() => regenerate(s.slot_id)}>
                      {regenBusy === s.slot_id ? "Regenerating…" : "Regenerate"}
                    </button>
                  </div>
                )}
                <div className="slot-purpose"><strong>Removes:</strong> {s.objective}</div>
                {uMap[s.primary_uncertainty_id] && (
                  <div className="sub" style={{ fontSize: 12, marginBottom: 8 }}>
                    ↳ doubt #{s.primary_uncertainty_id} (sev {uMap[s.primary_uncertainty_id].severity}): {uMap[s.primary_uncertainty_id].uncertainty}
                  </div>
                )}
                <div className="slot-prompt">{renderPrompt(s.prompt)}</div>
                {(s.prompt_constraints || []).length > 0 && (
                  <p className="sub" style={{ marginTop: 8, fontSize: 12 }}>Constraints: {s.prompt_constraints.join(" · ")}</p>
                )}
                <button className="btn-ghost" style={{ marginTop: 10 }} onClick={() => copy(renderPrompt(s.prompt))}>Copy prompt</button>
              </div>
            ))}
          </div>
        </div>
      )}


      {tab === "editor" && (
        <EditorTab listingId={id} output={out} price={data.input_price}
                   onSaved={() => window.dispatchEvent(new Event("lf:rescore"))} />
      )}
      {tab === "journey" && <JourneyTab listingId={id} genImages={genImages} />}
      {tab === "seo" && <SeoTab listingId={id} />}

      {tab === "publish" && (
        <PublishPanel listingId={id} defaultPrice={data.output?.product_analysis?.price_tier} />
      )}
      {tab === "export" && (
        <div className="card">
          <h2>Export</h2>
          <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
            <button className="btn" onClick={() => doExport("etsy")}>Etsy paste-ready</button>
            <button className="btn-ghost" onClick={() => doExport("images")}>Image production brief</button>
            <button className="btn-ghost" onClick={() => doExport("scorecard")}>Scorecard</button>
            <button className="btn-ghost" onClick={() => doExport("csv")}>CSV row</button>
          </div>
          <h2 style={{ marginTop: 22 }}>Download files</h2>
          <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
            <button className="btn" onClick={() => api.download(id, "zip")}>ZIP asset package</button>
            <button className="btn-ghost" onClick={() => api.download(id, "pdf")}>PDF report</button>
            <button className="btn-ghost" onClick={() => api.download(id, "csv")}>CSV</button>
            <button className="btn-ghost" onClick={() => api.download(id, "json")}>JSON</button>
          </div>
          {exported && <>
            <div className="copyblock">{exported}</div>
            <button className="btn-ghost" style={{ marginTop: 10 }} onClick={() => copy(exported)}>Copy to clipboard</button>
          </>}
        </div>
      )}
    </div>
  );
}


function PublishPanel({ listingId }) {
  const [status, setStatus] = useState(null);
  const [gate, setGate] = useState(null);
  const [price, setPrice] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [comp, setComp] = useState(null);
  const [compBusy, setCompBusy] = useState(false);

  useEffect(() => {
    api.etsyStatus().then(setStatus).catch(() => setStatus({ connected: false, configured: false }));
    api.etsyGate(listingId).then(setGate).catch((e) => setGate({ ok: false, blocks: [e.message] }));
  }, [listingId]);

  const connect = async () => {
    try {
      const { authorize_url } = await api.etsyConnect();
      window.location.href = authorize_url;
    } catch (e) { setError(e.message); }
  };

  const publish = async (activate) => {
    setBusy(true); setError(""); setResult(null);
    try {
      setResult(await api.etsyPublish(listingId, { price: Number(price), activate }));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const runCompetitive = async () => {
    setCompBusy(true); setError("");
    try { setComp(await api.etsyCompetitive(listingId)); }
    catch (e) { setError(e.message); } finally { setCompBusy(false); }
  };

  return (
    <>
      <div className="card">
        <h2>Etsy connection</h2>
        {status === null ? <p className="sub"><span className="spinner" />Checking…</p> : status.connected ? (
          <p className="sub" style={{ marginTop: 8 }}>
            <span className="pill green">connected</span>{" "}
            {status.shop_name || `shop ${status.shop_id}`}
          </p>
        ) : (
          <div style={{ marginTop: 10 }}>
            <p className="sub">{status.configured
              ? "Connect your Etsy shop to publish directly from ListingForge."
              : "Etsy API keys not configured on this server (set ETSY_API_KEY + ETSY_REDIRECT_URI)."}</p>
            {status.configured && <button className="btn" style={{ marginTop: 12 }} onClick={connect}>Connect Etsy shop</button>}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Pre-publish gate</h2>
        <p className="sub">Publishing is blocked until every requirement is met.</p>
        {gate === null ? <p className="sub"><span className="spinner" /></p> : gate.ok ? (
          <p style={{ marginTop: 10 }}><span className="pill green">all checks passed — ready to publish</span></p>
        ) : (
          <div style={{ marginTop: 8 }}>
            {gate.blocks.map((b, i) => (
              <div className="u-item" key={i}><div className="sev sev-5">✗</div><div>{b}</div></div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Publish</h2>
        <label className="field" style={{ maxWidth: 220 }}><span>Price (USD)</span>
          <input type="number" min="0.20" step="0.01" value={price}
                 onChange={(e) => setPrice(e.target.value)} placeholder="8.99" />
        </label>
        <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          <button className="btn-ghost" disabled={busy || !price || !gate?.ok || !status?.connected}
                  onClick={() => publish(false)}>Save as Etsy draft</button>
          <button className="btn" disabled={busy || !price || !gate?.ok || !status?.connected}
                  onClick={() => publish(true)}>
            {busy ? "Publishing…" : "Publish live"}
          </button>
        </div>
        {result && (
          <p style={{ marginTop: 14 }}>
            <span className="pill green">{result.state}</span>{" "}
            <a href={result.etsy_url} target="_blank" rel="noreferrer"
               style={{ color: "var(--gold-bright)" }}>{result.etsy_url}</a>
          </p>
        )}
        {error && <div className="error-text">{error}</div>}
      </div>

      <div className="card">
        <h2>Competitive analysis</h2>
        <p className="sub">Compares this listing against the top active Etsy results for your primary keyword.</p>
        <button className="btn-ghost" style={{ marginTop: 12 }} disabled={compBusy || !status?.connected}
                onClick={runCompetitive}>
          {compBusy ? "Analyzing…" : "Run analysis"}
        </button>
        {comp && (
          <div style={{ marginTop: 12 }}>
            <p className="sub mono">{comp.competitors_analyzed} competitors analyzed for “{comp.keyword}”</p>
            {comp.optimization_recommendations.map((r, i) => (
              <div className="u-item" key={i}>
                <div className="sev sev-3">→</div>
                <div>
                  <div className="sub mono" style={{ fontSize: 11.5 }}>{r.area}</div>
                  <div style={{ fontSize: 14 }}>{r.recommendation}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
