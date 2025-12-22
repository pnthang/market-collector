from app.vn_scraper import _parse_payload


def test_parse_simple_message():
    payload = '{"symbol":"VNINDEX","last":1200.5,"change":1.2,"percent":0.1}'
    res = _parse_payload(payload)
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["code"] == "VNINDEX"
    assert abs(res[0]["price"] - 1200.5) < 1e-6


def test_parse_nested_message():
    payload = '{"data":{"items":[{"symbol":"VN30","lastPrice":950.2}]}}'
    res = _parse_payload(payload)
    assert len(res) == 1
    assert res[0]["code"] == "VN30"
    assert abs(res[0]["price"] - 950.2) < 1e-6
