import dramatiq
from dramatiq.brokers.redis import RedisBroker

from .config import WorkerSettings


def initialize_broker(settings: WorkerSettings | None = None) -> RedisBroker:
    runtime_settings = settings or WorkerSettings()
    broker = RedisBroker(url=runtime_settings.redis_url.get_secret_value())
    dramatiq.set_broker(broker)
    return broker
