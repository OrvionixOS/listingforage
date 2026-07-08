import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

const KIND_ICON = { generation: "◆", publish: "▲", optimization: "→",
                    credits: "!", batch: "≡" };

export default function Notifications({ onOpen }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = () => api.notifications().then(setItems).catch(() => {});

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => { clearInterval(t); document.removeEventListener("mousedown", close); };
  }, []);

  const unread = items.filter((n) => !n.read);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && unread.length) {
      await api.markRead(unread.map((n) => n.id)).catch(() => {});
      setTimeout(load, 400);
    }
  };

  return (
    <div ref={ref} style={{ position: "relative", marginTop: 14 }}>
      <button className="nav-item" onClick={toggle} aria-haspopup="true"
              aria-expanded={open} aria-label={`Notifications, ${unread.length} unread`}>
        Notifications
        {unread.length > 0 && (
          <span className="pill gold" style={{ marginLeft: 8 }}>{unread.length}</span>
        )}
      </button>
      {open && (
        <div className="notif-panel" role="menu" aria-label="Notifications list">
          {items.length === 0 && <div className="sub" style={{ padding: 14 }}>Nothing yet.</div>}
          {items.slice(0, 12).map((n) => (
            <button key={n.id} className="notif-item" role="menuitem"
                    onClick={() => { setOpen(false); if (n.link && !n.link.startsWith("batch:")) onOpen(n.link); }}>
              <span className="notif-icon" aria-hidden="true">{KIND_ICON[n.kind] || "•"}</span>
              <span>
                <span style={{ display: "block", fontWeight: n.read ? 400 : 600 }}>{n.title}</span>
                {n.body && <span className="sub" style={{ fontSize: 12 }}>{n.body.slice(0, 90)}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
