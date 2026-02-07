"""Unit tests for mobile app client."""

from ui.mobile_app import MobileAppClient, MobileAppConfig


def test_mobile_app_build_url():
    client = MobileAppClient(MobileAppConfig(base_url="http://localhost:5000/"))
    assert client._build_url("/api/status") == "http://localhost:5000/api/status"


def test_mobile_app_headers_api_key():
    client = MobileAppClient(MobileAppConfig(api_key="test-key"))
    headers = client._headers()
    assert headers["Authorization"] == "Bearer test-key"
