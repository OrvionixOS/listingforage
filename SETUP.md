# Etsy Listing AI Studio — Deploy on Replit (iPad workflow)

No terminal on your machine needed. Everything below runs in Replit's Shell tab in Safari.

## 1. Create the Repl
- replit.com → Create Repl → **Import from upload** (or GitHub if you pushed it there)
- Upload `listingforge-ai-phase4.zip`, or unzip locally and drag the folder in
- Choose the **Python** template if asked

## 2. Add your secrets
Left sidebar → **Secrets** (padlock icon). Add:

| Key | Value | Required? |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | your Anthropic key | **Yes** — nothing generates without it |
| `FAL_KEY` | your fal.ai key | Optional — omit to use the built-in local image renderer |
| `ETSY_API_KEY` | your Etsy app keystring | Optional — needed only to publish |
| `ETSY_REDIRECT_URI` | `https://YOUR-REPL-URL/api/etsy/callback` | Optional — must match your Etsy app settings |

## 3. Install + build (Shell tab)
Run these four commands one at a time:

    cd backend && pip install -r requirements.txt
    cd ../frontend && npm install
    npm run build
    cd ../backend

The `npm run build` step compiles the React app into `frontend/dist`, which the
backend serves automatically — so you only ever run ONE server.

## 4. Start the server
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Replit opens a web preview. That URL is your live app.

## 5. First run
- Sign up with any email + password (creates your account)
- New listing → upload your digital product → watch the full pipeline
- Without `FAL_KEY` it uses the local renderer (real pixels, no cost) — perfect for testing

## Making it permanent
- **Run button**: create a `.replit` file with
  `run = "cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"`
- **Always-on**: enable Replit's Autoscale/Reserved VM deployment so it doesn't sleep
- Data lives in `backend/listingforge.db` (SQLite). Fine to start; Phase 5 migrates to Postgres.

## If something breaks
- `ANTHROPIC_API_KEY` missing → generation fails immediately. Check Secrets.
- `vite: not found` → you skipped `npm install` in the frontend folder.
- Blank page but API works → you skipped `npm run build`.
- Port conflict → Replit sometimes wants port 3000; change `--port` to match the preview.
