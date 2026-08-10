from common.rpc import dumps, loads


def test_json_rpc_roundtrip():
    payload = {"machine_id": "m1", "replicas": 4, "healthy": True}
    assert loads(dumps(payload)) == payload
