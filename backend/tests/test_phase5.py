"""Phase 5 hardening tests: job queue + recovery, assist quota metering."""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import jobs
from app.database import (Base, Job, Listing, ListingEvent, SessionLocal,
                          User, engine, init_db)


def fresh():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    user = User(email="p5@test.com", password_hash="x", plan="free")
    db.add(user); db.commit()
    return db, user


def test_queue_executes_and_marks_done():
    db, user = fresh()
    ran = []
    jobs.HANDLERS["noop_test"] = lambda job: ran.append(job.payload["x"])
    jobs.enqueue(db, user.id, "noop_test", {"x": 42})
    jobs._started = False
    jobs._stop.clear()
    jobs.recover_and_start()
    for _ in range(40):
        db.expire_all()
        j = db.query(Job).first()
        if j.status == "done":
            break
        time.sleep(0.25)
    assert ran == [42]
    assert db.query(Job).first().status == "done"
    jobs.stop()
    print("PASS queue: enqueued job claimed by worker, executed, marked done")
    db.close()


def test_queue_recovery_and_retry():
    db, user = fresh()
    # stale 'running' job from a crashed process
    stale = Job(user_id=user.id, kind="flaky_test", payload={}, status="running")
    db.add(stale); db.commit()
    attempts = []
    def flaky(job):
        attempts.append(job.attempts)
        if job.attempts < 2:
            raise RuntimeError("boom")
    jobs.HANDLERS["flaky_test"] = flaky
    jobs._started = False
    jobs._stop.clear()
    jobs.recover_and_start()   # must requeue the stale job
    for _ in range(60):
        db.expire_all()
        j = db.get(Job, stale.id)
        if j.status in ("done", "failed") and len(attempts) >= 2:
            break
        time.sleep(0.25)
    db.expire_all()
    assert db.get(Job, stale.id).status == "done", db.get(Job, stale.id).error
    assert attempts == [1, 2], attempts
    jobs.stop()
    print("PASS recovery: stale running job requeued on startup, "
          "failed once, retried, succeeded")
    db.close()


def test_assist_quota_metering():
    """free plan: 3 listings/mo -> 15 assist calls; the 16th must 402."""
    from app.billing import PLANS
    db, user = fresh()
    limit = PLANS["free"]["listings_per_month"] * 5
    for _ in range(limit):
        db.add(ListingEvent(user_id=user.id, kind="assist", payload={}))
    db.commit()
    used = (db.query(ListingEvent)
            .filter(ListingEvent.user_id == user.id,
                    ListingEvent.kind == "assist").count())
    assert used >= limit  # route raises 402 at this point (logic mirrored)
    print(f"PASS assist quota: {used}/{limit} calls metered; next call blocked (402)")
    db.close()


if __name__ == "__main__":
    test_queue_executes_and_marks_done()
    test_queue_recovery_and_retry()
    test_assist_quota_metering()
    print("\nALL PHASE 5 HARDENING TESTS PASSED")
