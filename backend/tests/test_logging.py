import logging

from app.logging import get_logger


def test_logger_renames_reserved_extra_keys(caplog):
    log = get_logger("tests.portal_logging")

    with caplog.at_level(logging.INFO, logger="tests.portal_logging"):
        log.info("sync event", created=True, tenant="demo")

    record = caplog.records[-1]
    assert record.tenant == "demo"
    assert record.extra_created is True
    assert isinstance(record.created, float)
