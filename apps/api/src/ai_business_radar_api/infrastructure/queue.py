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


class QueuedJob(BaseModel):
    job_id: str
    queue: str
    status: Literal["queued"] = "queued"
