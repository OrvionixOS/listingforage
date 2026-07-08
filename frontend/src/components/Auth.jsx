import { useState } from "react";
import { api, setToken } from "../lib/api";

export default function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setError("");
    try {
      const fn = mode === "login" ? api.login : api.register;
      const { access_token } = await fn(email, password);
      setToken(access_token);
      onAuthed();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="wordmark">Listing<em>Forge</em></div>
        <div className="tagline">E-commerce conversion intelligence</div>
        <div className="card">
          <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
          <label className="field"><span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="email" />
          </label>
          <label className="field"><span>Password{mode === "register" ? " (8+ characters)" : ""}</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              onKeyDown={(e) => e.key === "Enter" && submit()} />
          </label>
          {error && <div className="error-text">{error}</div>}
          <div style={{ marginTop: 18, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <button className="btn" onClick={submit} disabled={busy || !email || password.length < 8}>
              {busy ? "One moment…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
            <button className="btn-ghost"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
              {mode === "login" ? "New here? Create account" : "Have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
