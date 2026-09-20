"""Small durable queue: bounded workers, atomic claims and renewable leases.

Each worker owns its own database session. SQL is the source of truth; the
executor is only a runner. An interrupted lease is reclaimable after 60 seconds.
"""
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.tables import PipelineJobRow, PipelineRunRow

logger = logging.getLogger(__name__)
LEASE_SECONDS = 60
worker_batch: ContextVar[str | None] = ContextVar("worker_batch", default=None)


def enqueue(db: Session, batch_id: str) -> None:
    job = db.get(PipelineJobRow, batch_id)
    if job is None:
        db.add(PipelineJobRow(batch_id=batch_id, status="QUEUED", generation=1))
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
    # A new request during execution causes one more pass after the current pass.
    db.execute(update(PipelineJobRow).where(PipelineJobRow.batch_id == batch_id)
               .values(generation=PipelineJobRow.generation + 1))
    db.execute(update(PipelineJobRow).where(PipelineJobRow.batch_id == batch_id,
                                          PipelineJobRow.status != "RUNNING")
               .values(status="QUEUED"))
    db.commit()


def claim(db: Session) -> tuple[str, str, int] | None:
    now = datetime.now(timezone.utc)
    available = or_(PipelineJobRow.status == "QUEUED",
                    (PipelineJobRow.status == "RUNNING") & (PipelineJobRow.lease_until < now))
    batch_id = db.scalar(select(PipelineJobRow.batch_id).where(available).order_by(PipelineJobRow.updated_at).limit(1))
    if batch_id is None:
        return None
    token = str(uuid4())
    result = db.execute(update(PipelineJobRow).where(PipelineJobRow.batch_id == batch_id, available)
                        .values(status="RUNNING", lease_token=token,
                                lease_until=now + timedelta(seconds=LEASE_SECONDS)))
    db.commit()
    if result.rowcount != 1:
        return None
    db.expire_all()
    job = db.get(PipelineJobRow, batch_id)
    assert job is not None
    return batch_id, token, job.generation


def execute(batch_id: str, token: str, generation: int) -> None:
    from app.api.pipeline import advance_pipeline, decide_push, PushDecision, PushDecisionRequest

    failed = False
    context_token = worker_batch.set(batch_id)
    try:
        with SessionLocal() as db:
            pipeline = db.get(PipelineRunRow, batch_id)
            if pipeline is None or pipeline.status in {"CANCELLED", "COMPLETED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK", "PARTIAL_FAILURE"}:
                return
            result = advance_pipeline(batch_id, False, db)
            if result.execution_mode == "AUTOPILOT" and (result.status == "AWAITING_PUSH_DECISION" or result.current_stage == "push" and result.status == "FAILED"):
                decide_push(batch_id, PushDecisionRequest(decision=PushDecision.PUSH), db)
    except Exception:
        failed = True
        # No raw data or provider exception text in logs.
        logger.warning("Migration worker stopped; batch=%s", batch_id)
    finally:
        worker_batch.reset(context_token)
        with SessionLocal() as db:
            job = db.scalar(select(PipelineJobRow).where(PipelineJobRow.batch_id == batch_id, PipelineJobRow.lease_token == token))
            if job is not None:
                job.status = "QUEUED" if job.generation > generation else "FAILED" if failed else "WAITING"
                job.lease_token = None
                job.lease_until = None
                db.commit()


class JobRunner:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="migration-dispatcher")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def _loop(self) -> None:
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="migration")
        active: dict[Future, tuple[str, str, int]] = {}
        try:
            while not self.stop_event.is_set():
                try:
                    active = {future: task for future, task in active.items() if not future.done()}
                    with SessionLocal() as db:
                        for batch_id, token, _ in active.values():
                            db.execute(update(PipelineJobRow).where(PipelineJobRow.batch_id == batch_id, PipelineJobRow.lease_token == token)
                                       .values(lease_until=datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)))
                        db.commit()
                        if len(active) < 2:
                            task = claim(db)
                            if task:
                                active[pool.submit(execute, *task)] = task
                except Exception:
                    logger.warning("Migration dispatcher will retry database access")
                self.stop_event.wait(0.5)
        finally:
            pool.shutdown(wait=True)
