from shared.streamhub_common.service_client import ServiceClient

from .config import CONTENT_SERVICE_URL, USER_SERVICE_URL


_user_client: ServiceClient | None = None
_content_client: ServiceClient | None = None


def get_user_client() -> ServiceClient:
    global _user_client
    if _user_client is None:
        _user_client = ServiceClient(USER_SERVICE_URL)
    return _user_client


def get_content_client() -> ServiceClient:
    global _content_client
    if _content_client is None:
        _content_client = ServiceClient(CONTENT_SERVICE_URL)
    return _content_client


async def close_clients() -> None:
    global _user_client, _content_client
    if _user_client is not None:
        await _user_client.aclose()
        _user_client = None
    if _content_client is not None:
        await _content_client.aclose()
        _content_client = None
