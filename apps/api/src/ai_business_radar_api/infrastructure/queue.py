from typing import Any, Literal

from dramatiq import Message
from dramatiq.brokers.redis import RedisBroker
from pydantic import BaseModel


class QueueUnavailableError(RuntimeError):
    pass


class JobEnqueuer:
    def __init__(self, redis_url: str) -> None:
        self._broker = RedisBroker(url=redis_url)

    def enqueue(self, *, queue: str, actor: str, payload: dict[str, Any]) -> str:
        message = Message(queue_name=queue, actor_name=actor, args=(), kwargs=payload, options={})
        try:
            self._broker.enqueue(message)
        except Exception as error:
            raise QueueUnavailableError("Collection queue is unavailable") from error
        return message.message_id

    def enqueue_unique(
        self,
        *,
        queue: str,
        actor: str,
        payload: dict[str, Any],
        deduplication_key: str,
        ttl_seconds: int = 900,
    ) -> str | None:
        """Acquire a bounded Redis lease before enqueueing duplicate-prone maintenance work."""
        key = f"ai-business-radar:job-dedup:{deduplication_key}"
        try:
            acquired = self._broker.client.set(key, "1", ex=ttl_seconds, nx=True)
            if not acquired:
                return None
            try:
                return self.enqueue(queue=queue, actor=actor, payload=payload)
            except Exception:
                self._broker.client.delete(key)
                raise
        except QueueUnavailableError:
            raise
        except Exception as error:
            raise QueueUnavailableError("Collection queue is unavailable") from error


class QueuedJob(BaseModel):
    job_id: str
    queue: str
    status: Literal["queued"] = "queued"
