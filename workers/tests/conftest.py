import dramatiq
from dramatiq.brokers.stub import StubBroker


def pytest_configure() -> None:
    dramatiq.set_broker(StubBroker())
