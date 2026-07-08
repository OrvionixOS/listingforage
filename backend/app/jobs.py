"""
DB-backed background job queue (Phase 5 hardening).

Replaces raw threads for generation work. Jobs live in the `jobs` table, so a
server restart no longer strands work: on startup, stale `running` jobs are
reset to `queued` and workers resume them.

Kinds:
  generate_listing — payload: {listing_id, req: GenerateRequest dict,
                               image_paths: [], batch_id?: str}

Bulk generation enqueues one job per item; when the last job of a batch
finishes, the batch notification fires.
"""
from __future__ import annotations

import logging
import threading
import time

from .database import Job, Listing, SessionLocal

log = logging.getLogger("listingforge.jobs")

WORKERS = 2
POLL_SECONDS = 1.5
MAX_ATTEMPTS = 2

_started = False
_stop = threading.Event()
_lock = threading.Lock()


def enqueue(db, user_id: str, kind: str, payload: dict) -> Job:
    job = Job(user_id=user_id, kind=kind, payload=payload)
    db.add(job)
    db.commit()
    return job


def _claim(db) -> Job | None:
    with _lock:  # single-process claim guard (SQLite dev)
        job = (db.query(Job).filter(Job.status == "queued")
               .order_by(Job.created_at).first())
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        db.commit()
        return job


def _run_generate_listing(job: Job) -> None:
    from .routes.listing_routes import _run_pipeline
    from .schemas import GenerateRequest

    p = job.payload or {}
    req = GenerateRequest(**p["req"])
    _run_pipeline(p["listing_id"], job.user_id, req, p.get("image_paths", []))

    batch_id = p.get("batch_id")
    if batch_id:
        _maybe_finish_batch(batch_id, job.user_id)


def _maybe_finish_batch(batch_id: str, user_id: str) -> None:
    db = SessionLocal()
    try:
        rows = db.query(Listing).filter(Listing.batch_id == batch_id).all()
        if rows and all(r.status in ("complete", "failed") for r in rows):
            from .notify import notify_batch
            done = sum(1 for r in rows if r.status == "complete")
            failed = sum(1 for r in rows if r.status == "failed")
            notify_batch(db, user_id, batch_id, done, failed)
    finally:
        db.close()


HANDLERS = {"generate_listing": _run_generate_listing}


def _worker(idx: int) -> None:
    log.info("job worker %d online", idx)
    while not _stop.is_set():
        db = SessionLocal()
        job = None
        try:
            job = _claim(db)
            if job is None:
                db.close()
                time.sleep(POLL_SECONDS)
                continue
            log.info("worker %d: job %s (%s) attempt %d",
                     idx, job.id, job.kind, job.attempts)
            handler = HANDLERS.get(job.kind)
            if handler is None:
                raise ValueError(f"no handler for job kind {job.kind}")
            handler(job)
            job.status = "done"
            job.error = None
            db.commit()
        except Exception as exc:
            log.exception("job failed")
            if job is not None:
                job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
                job.error = str(exc)[:2000]
                db.commit()
        finally:
            db.close()


def recover_and_start() -> None:
    """Called on app startup: requeue stale running jobs, start workers."""
    global _started
    if _started:
        return
    _started = True
    db = SessionLocal()
    try:
        stale = db.query(Job).filter(Job.status == "running").all()
        for j in stale:
            j.status = "queued"
        # listings stuck in 'generating' with no live job = crashed mid-run;
        # their queued job (if any) will rerun the pipeline.
        if stale:
            log.info("recovered %d interrupted job(s)", len(stale))
        db.commit()
    finally:
        db.close()
    for i in range(WORKERS):
        threading.Thread(target=_worker, args=(i,), daemon=True,
                         name=f"lf-worker-{i}").start()


def stop() -> None:
    _stop.set()
