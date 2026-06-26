import httpx

from jqcli.api.client import ApiClient
from jqcli.api.live import get_live_logs, get_live_positions, list_live_trades


def client_with(handler):
    return ApiClient("https://example.test", token="tok", transport=httpx.MockTransport(handler))


def test_list_live_trades_running():
    def handler(request):
        assert request.url.path == "/algorithm/trade/list"
        assert request.url.params["process"] == "1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "liveArr": [
                        {
                            "backtestId": "live1",
                            "name": "模拟A",
                            "status": "1",
                            "frequency": "day",
                            "baseCapital": "1000000",
                            "startTime": "2026-06-22 00:00:00",
                            "isNotice": True,
                        }
                    ],
                    "totalCount": "1",
                    "totalLiveCount": "3",
                    "remainLiveCount": "2",
                    "isBindWechat": 1,
                },
                "status": "0",
                "code": "00000",
            },
        )

    payload = list_live_trades(client_with(handler))

    assert payload["items"][0]["id"] == "live1"
    assert payload["items"][0]["status"] == "running"
    assert payload["items"][0]["capital"] == 1000000
    assert payload["remain_live_count"] == 2


def test_get_live_positions():
    def handler(request):
        assert request.url.path == "/algorithm/live/position"
        assert request.url.params["backtestId"] == "live1"
        assert request.url.params["isForward"] == "1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "position": [
                        {
                            "security": "基金",
                            "stock": "纳指ETF(513100.XSHG)",
                            "side": "多",
                            "amount": "100股",
                            "closeableAmount": "100股",
                            "price": "2.365",
                            "value": 236.5,
                            "gain": 10,
                            "gainPercent": 0.0442,
                            "gainPercentStr": "4.42%",
                            "avgCost": "2.265",
                            "positionPersent": "100.0%",
                        }
                    ],
                    "cash": 1000,
                    "totalValue": 1236.5,
                    "isLimit": False,
                },
                "status": "0",
                "code": "00000",
            },
        )

    payload = get_live_positions(client_with(handler), "live1")

    assert payload["cash"] == 1000
    assert payload["total_value"] == 1236.5
    assert payload["positions"][0]["code"] == "513100.XSHG"
    assert payload["positions"][0]["name"] == "纳指ETF"


def test_get_live_logs_latest():
    def handler(request):
        assert request.url.path == "/algorithm/live/log"
        assert request.url.params["backtestId"] == "live1"
        assert request.url.params["offset"] == "-1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "offset": 2,
                    "state": "1",
                    "logArr": [
                        "2026-06-22 09:30:00 - INFO  - 启动",
                        "2026-06-22 14:29:00 - WARNING - 测试",
                    ],
                },
                "status": "0",
                "code": "00000",
            },
        )

    payload = get_live_logs(client_with(handler), "live1", limit=1)

    assert payload["count"] == 1
    assert payload["logs"][0]["level"] == "WARNING"
    assert payload["logs"][0]["message"] == "测试"


def test_get_live_logs_by_date_pages_backwards():
    seen = []

    def handler(request):
        seen.append((request.url.path, dict(request.url.params)))
        if request.url.params["offset"] == "-1":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "offset": 2,
                        "state": "1",
                        "logArr": ["2026-06-23 09:30:00 - INFO  - newer"],
                    },
                    "status": "0",
                    "code": "00000",
                },
            )
        assert request.url.params["addLog"] == "1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "offset": 0,
                    "state": "1",
                    "logArr": ["2026-06-22 09:30:00 - INFO  - target"],
                },
                "status": "0",
                "code": "00000",
            },
        )

    payload = get_live_logs(client_with(handler), "live1", date="2026-06-22")

    assert payload["logs"][0]["message"] == "target"
    assert payload["pages_read"] == 2
    assert seen[1][1]["offset"] == "0"
