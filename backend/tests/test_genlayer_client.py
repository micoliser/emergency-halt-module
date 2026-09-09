"""
Transport-level tests for the read-only GenLayer client.

The request shape here was verified against studionet
(`https://studio.genlayer.com/api`): an unknown contract answers with RPC
error -32001, which proves the calldata + `from` fields are accepted.
"""

import json

import pytest
import requests
from genlayer_py.abi import calldata

from apps.sync.genlayer_client import (
    ContractCallError,
    GenLayerError,
    HaltModuleReader,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, text=None):
        self._payload = payload
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Records requests and replays a queue of canned responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, json=None, timeout=None):  # noqa: A002 - requests' kwarg name
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _encoded(value) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "result": calldata.encode(value).hex()}


def _reader(responses, **kwargs) -> tuple[HaltModuleReader, FakeSession]:
    session = FakeSession(responses)
    reader = HaltModuleReader(
        rpc_url="https://studio.genlayer.com/api",
        contract_address="0x" + "ab" * 20,
        reader_address="0x" + "11" * 20,
        throttle_seconds=0,
        max_retries=3,
        session=session,
        **kwargs,
    )
    return reader, session


def test_view_call_builds_a_gen_call_read_request():
    reader, session = _reader([FakeResponse(_encoded(3))])

    assert reader.get_protocol_count() == 3

    sent = session.requests[0]["json"]
    assert sent["method"] == "gen_call"
    params = sent["params"][0]
    assert params["type"] == "read"
    assert params["to"] == "0x" + "ab" * 20
    assert params["from"] == "0x" + "11" * 20
    assert params["transaction_hash_variant"] == "latest-nonfinal"
    assert params["data"].startswith("0x")


def test_arguments_are_encoded_into_the_calldata():
    reader, session = _reader([FakeResponse(_encoded({"id": 0}))])

    reader.get_protocol(0)

    # rlp([calldata, b"\x00"]) — the method + args survive a decode round trip.
    payload = session.requests[0]["json"]["params"][0]["data"]
    assert "get_protocol" in bytes.fromhex(payload[2:]).decode("latin-1")


def test_decodes_dicts_lists_and_bools():
    protocol = {"id": 0, "status": "HALTED", "reporter_bond": 10**18}
    reader, _ = _reader(
        [
            FakeResponse(_encoded(protocol)),
            FakeResponse(_encoded([protocol])),
            FakeResponse(_encoded(True)),
        ]
    )

    assert reader.get_protocol(0) == protocol
    assert reader.list_protocols(0, 20) == [protocol]
    assert reader.is_action_allowed(0, "withdraw") is True


def test_0x_prefixed_results_decode():
    reader, _ = _reader(
        [
            FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": "0x" + calldata.encode(7).hex(),
                }
            )
        ]
    )

    assert reader.get_case_count() == 7


def test_contract_revert_raises_contract_call_error():
    reader, _ = _reader(
        [
            FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32000, "message": "Protocol does not exist"},
                }
            )
        ]
    )

    with pytest.raises(ContractCallError, match="Protocol does not exist"):
        reader.get_protocol(9)


def test_rate_limit_is_retried_then_succeeds():
    rate_limited = FakeResponse(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32006, "message": "too many requests"},
        }
    )
    reader, session = _reader([rate_limited, FakeResponse(_encoded(1))])

    assert reader.get_protocol_count() == 1
    assert len(session.requests) == 2


def test_http_429_is_retried():
    reader, session = _reader(
        [FakeResponse({}, status_code=429), FakeResponse(_encoded(2))]
    )

    assert reader.get_protocol_count() == 2
    assert len(session.requests) == 2


def test_exhausted_retries_raise_genlayer_error():
    reader, session = _reader([FakeResponse({}, status_code=503)] * 3)

    with pytest.raises(GenLayerError, match="HTTP 503"):
        reader.get_protocol_count()
    assert len(session.requests) == 3


def test_transport_errors_are_wrapped():
    reader, _ = _reader([requests.ConnectionError("boom")] * 3)

    with pytest.raises(GenLayerError, match="transport error"):
        reader.get_protocol_count()


def test_missing_contract_address_fails_fast():
    reader, session = _reader([])
    reader.contract_address = ""

    with pytest.raises(GenLayerError, match="HALT_MODULE_ADDRESS"):
        reader.get_protocol_count()
    assert session.requests == []
