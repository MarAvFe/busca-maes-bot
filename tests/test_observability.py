"""Unit tests for correlation ID and JSON logging setup."""

import json
import logging

from buscamaes.observability import (
    CorrelationIdFilter,
    configure_logging,
    correlation_id,
    new_correlation_id,
)


def test_new_correlation_id_returns_12_char_hex():
    cid = new_correlation_id()
    assert len(cid) == 12
    assert all(c in "0123456789abcdef" for c in cid)


def test_correlation_id_default_is_dash():
    val = correlation_id.get()
    assert isinstance(val, str)


def test_filter_injects_correlation_id_onto_record():
    new_correlation_id()
    expected = correlation_id.get()
    f = CorrelationIdFilter()
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)
    assert f.filter(record) is True
    assert record.correlation_id == expected


def test_configure_logging_emits_json(capsys):
    configure_logging("INFO")
    new_correlation_id()
    cid = correlation_id.get()
    logging.getLogger("test_logger").info("hello world")
    captured = capsys.readouterr()
    output = captured.err or captured.out
    line = output.strip().split("\n")[-1]
    parsed = json.loads(line)
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["correlation_id"] == cid
