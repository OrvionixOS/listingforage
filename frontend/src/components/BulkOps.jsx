import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

export default function BulkOps({ onOpen }) {
  const [raw, setRaw] = useState("");
  const [items, setItems] = useState([]);
  const [batch, setBatch] = useState(null);
  const [err, setErr] = useState("");
  const timer = useRef(null);

  // Parse lines: Title | description | price(optional)
  const parse = (text) => {
    setRaw(text);
    const rows = text.split("\n").map((l) => l.trim()).filter(Boolean).map((line) => {
      const [title = "", description = "", price = ""] = line.split("|").map((s) => s.trim());
      return { title, description, price: price ? Number(price) : undefined };
    });
    setItems(rows);
  };

  const start = async () => {
    setErr("");
    try {
      const r = await api.bulkGenerate(items);
      setBatch({ batch_id: r.batch_id, items: [] });
    } catch (e) { setErr(e.message); }
  };

  useEffect(() => {
    if (!batch?.batch_id) return;
    const poll = async () => {
      try {
        const s = await api.bulkStatus(batch.batch_id);
        setBatch(s);
        if (s.done && timer.current) clearInterval(timer.current);
      } catch { /* keep polling */ }
    };
    poll();
    timer.current = setInterval(poll, 4000);
    return () => clearInterval(timer.current);
  }, [batch?.batch_id]);

  const valid = items.length > 0 && items.every((i) => i.title && i.description);

  return (
    <>
      <h1>Bulk generate</h1>
      <p className="sub">One line per product: <span className="mono">Title | description | price</span>.
        Each line runs the full 11-step pipeline in the background.</p>

      {!batch && (
        <div className="card">
          <textarea rows={8} value={raw} onChange={(e) => parse(e.target.value)}
            aria-label="Bulk product lines"
            placeholder={"Liquid Gold Foil Paper | 12 seamless gold textures, 300 DPI | 8.99\nMarble Luxe Pack | 10 gold-vein marble digital papers | 7.49"}
            style={{ width: "100%" }} />
          <div style={{ display: "flex", justifyContent: "space-between",
                        alignItems: "center", marginTop: 12 }}>
            <span className="sub mono">{items.length} item(s) parsed
              {items.length > 0 && !valid && " — every line needs title | description"}</span>
            <button className="btn" disabled={!valid || items.length > 25} onClick={start}>
              Generate {items.length || ""} listing{items.length === 1 ? "" : "s"}
            </button>
          </div>
          {err && <div className="error-text">{err}</div>}
        </div>
      )}

      {batch && (
        <div className="card">
          <h2>Batch {batch.batch_id}</h2>
          {batch.done && <p style={{ marginTop: 8 }}><span className="pill green">batch complete</span></p>}
          {(batch.items || []).map((l) => (
            <div className="listing-row" key={l.id}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>{l.title}</div>
                {l.status === "generating" && l.progress && (
                  <div className="sub mono" style={{ fontSize: 12 }}>
                    step {l.progress.index}/{l.progress.total}: {l.progress.step.replace(/_/g, " ")}
                  </div>
                )}
                {l.error && <div className="sub" style={{ color: "var(--red)", fontSize: 12 }}>{l.error}</div>}
              </div>
              <span className={`pill ${l.status === "complete" ? "green" : l.status === "failed" ? "red" : "gold"}`}>
                {l.status}</span>
              {l.status === "complete" && (
                <button className="btn-ghost" onClick={() => onOpen(l.id)}>Open</button>
              )}
            </div>
          ))}
          {batch.done && (
            <button className="btn-ghost" style={{ marginTop: 12 }}
                    onClick={() => { setBatch(null); setRaw(""); setItems([]); }}>
              Start another batch
            </button>
          )}
        </div>
      )}
    </>
  );
}
