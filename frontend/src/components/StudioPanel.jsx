import { useState } from "react";
import { api } from "../lib/api";

export default function StudioPanel({ listingId, slots, genImages, reload }) {
  const ordered = Object.values(genImages)
    .sort((a, b) => (a.meta.display_order || 99) - (b.meta.display_order || 99));

  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [mobile, setMobile] = useState(false);
  const [openSlot, setOpenSlot] = useState(null);   // slot id with detail drawer open
  const [versions, setVersions] = useState({});     // slot -> [{...,blobUrl}]
  const [prompts, setPrompts] = useState({});       // slot -> edited prompt text

  const slotById = Object.fromEntries(slots.map((s) => [s.slot_id, s]));

  const move = async (slotId, dir) => {
    const seq = ordered.map((g) => g.meta.slot_id);
    const i = seq.indexOf(slotId);
    const j = i + dir;
    if (j < 0 || j >= seq.length) return;
    [seq[i], seq[j]] = [seq[j], seq[i]];
    setBusy("reorder"); setErr("");
    try {
      await api.reorderImages(listingId, seq.map((sid, k) => ({ slot_id: sid, display_order: k + 1 })));
      await reload();
    } catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  const regen = async (slotId) => {
    setBusy("regen" + slotId); setErr("");
    try { await api.regenerateImage(listingId, slotId); await reload(); }
    catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  const regenCustom = async (slotId) => {
    setBusy("custom" + slotId); setErr("");
    try {
      const r = await api.regenerateCustom(listingId, slotId, prompts[slotId]);
      if (!r.passed) setErr(`Rendered, but pixel validation flagged: ${r.failures.join("; ")}`);
      await reload();
      await loadVersions(slotId);
    } catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  const loadVersions = async (slotId) => {
    const rows = await api.imageVersions(listingId, slotId);
    const withBlobs = await Promise.all(rows.slice(0, 4).map(async (v) => ({
      ...v, blobUrl: await api.versionBlob(listingId, slotId, v.image_id).catch(() => null),
    })));
    setVersions((p) => ({ ...p, [slotId]: withBlobs }));
  };

  const openDrawer = async (slotId, currentPrompt) => {
    if (openSlot === slotId) { setOpenSlot(null); return; }
    setOpenSlot(slotId);
    setPrompts((p) => ({ ...p, [slotId]: p[slotId] ?? currentPrompt }));
    await loadVersions(slotId).catch(() => {});
  };

  const restore = async (slotId, imageId) => {
    setBusy("restore"); setErr("");
    try { await api.restoreVersion(listingId, slotId, imageId); await reload(); await loadVersions(slotId); }
    catch (e) { setErr(e.message); } finally { setBusy(""); }
  };

  const size = mobile ? 96 : undefined;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Image studio</h2>
        <label style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={mobile} onChange={(e) => setMobile(e.target.checked)} />
          <span className="sub">Mobile thumbnail preview (180px grid)</span>
        </label>
      </div>
      <p className="sub">The Etsy sequence, in order. Position 1 is your search thumbnail.</p>

      {/* Etsy listing preview strip */}
      <div style={{ display: "flex", gap: 8, margin: "14px 0", overflowX: "auto" }}
           aria-label="Etsy listing preview strip">
        {ordered.map((g) => (
          <img key={g.meta.slot_id} src={g.blobUrl} alt={`position ${g.meta.display_order}`}
               loading="lazy"
               style={{ width: 64, height: 64, borderRadius: 6, objectFit: "cover",
                        border: g.meta.display_order === 1
                          ? "2px solid var(--gold)" : "1px solid var(--hairline)" }} />
        ))}
      </div>

      {err && <div className="error-text">{err}</div>}

      <div className={mobile ? "studio-grid mobile" : "studio-grid"}>
        {ordered.map((g, idx) => {
          const s = slotById[g.meta.slot_id];
          const sc = g.meta.scores || {};
          return (
            <div className="studio-cell" key={g.meta.slot_id}>
              <img src={g.blobUrl} alt={`slot ${g.meta.slot_id} image`} loading="lazy"
                   style={{ width: size || "100%", height: size, borderRadius: 8,
                            border: "1px solid var(--hairline)", objectFit: "cover" }} />
              <div style={{ fontWeight: 600, marginTop: 8 }}>
                #{g.meta.display_order} · {s?.required_visual_type}
              </div>
              <div className="sub" style={{ fontSize: 12.5, marginTop: 2 }}>
                <strong>Purpose:</strong> {s?.objective}
              </div>
              <div className="sub mono" style={{ fontSize: 11.5, marginTop: 4 }}>
                stage: {s?.psychological_stage} · pixel {g.meta.validation_score}/100
                {g.meta.regeneration_count > 0 && ` · ${g.meta.regeneration_count} regen`}
              </div>
              <div className="sub mono" style={{ fontSize: 11 }}>
                ctr {sc.ctr_effectiveness} · trust {sc.trust_level} · thumb {sc.thumbnail_readability}
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                <button className="btn-ghost" aria-label="Move earlier" disabled={idx === 0 || !!busy}
                        onClick={() => move(g.meta.slot_id, -1)}>↑</button>
                <button className="btn-ghost" aria-label="Move later"
                        disabled={idx === ordered.length - 1 || !!busy}
                        onClick={() => move(g.meta.slot_id, 1)}>↓</button>
                <button className="btn-ghost" disabled={!!busy} onClick={() => regen(g.meta.slot_id)}>
                  {busy === "regen" + g.meta.slot_id ? "…" : "Regenerate"}
                </button>
                <button className="btn-ghost" onClick={() => openDrawer(g.meta.slot_id, g.meta.generation_prompt)}
                        aria-expanded={openSlot === g.meta.slot_id}>
                  {openSlot === g.meta.slot_id ? "Close" : "Prompt & versions"}
                </button>
              </div>

              {openSlot === g.meta.slot_id && (
                <div style={{ marginTop: 10 }}>
                  <textarea rows={6} value={prompts[g.meta.slot_id] || ""}
                            aria-label="Generation prompt"
                            onChange={(e) => setPrompts((p) => ({ ...p, [g.meta.slot_id]: e.target.value }))}
                            style={{ width: "100%", fontSize: 12 }} className="mono" />
                  <button className="btn" style={{ marginTop: 8 }}
                          disabled={!!busy || (prompts[g.meta.slot_id] || "").length < 30}
                          onClick={() => regenCustom(g.meta.slot_id)}>
                    {busy === "custom" + g.meta.slot_id ? "Rendering…" : "Render edited prompt"}
                  </button>
                  {(versions[g.meta.slot_id] || []).length > 1 && (
                    <>
                      <div className="sub" style={{ marginTop: 12, fontWeight: 600 }}>Versions</div>
                      <div style={{ display: "flex", gap: 8, marginTop: 6, overflowX: "auto" }}>
                        {(versions[g.meta.slot_id] || []).map((v) => (
                          <div key={v.image_id} style={{ textAlign: "center" }}>
                            {v.blobUrl && <img src={v.blobUrl} alt="version" loading="lazy"
                              style={{ width: 72, height: 72, borderRadius: 6, objectFit: "cover",
                                       border: v.live ? "2px solid var(--gold)" : "1px solid var(--hairline)" }} />}
                            <div className="sub mono" style={{ fontSize: 10.5 }}>{v.validation_score}/100</div>
                            {!v.live && (
                              <button className="btn-ghost" style={{ fontSize: 11, padding: "2px 8px" }}
                                      disabled={!!busy}
                                      onClick={() => restore(g.meta.slot_id, v.image_id)}>Restore</button>
                            )}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {ordered.length === 0 && <p className="sub">Images are still generating for this listing.</p>}
    </div>
  );
}
