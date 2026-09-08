import logging

from ai_business_radar_api.logging import configure_logging


def test_provider_http_loggers_do_not_emit_request_urls_at_info() -> None:
    configure_logging("INFO")
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
