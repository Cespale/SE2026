from shared.streamhub_common.service_client import ServiceClient

from .config import SOCIAL_SERVICE_URL, USER_SERVICE_URL


_user_client: ServiceClient | None = None
_social_client: ServiceClient | None = None


def get_user_client() -> ServiceClient:
    global _user_client
    if _user_client is None:
        _user_client = ServiceClient(USER_SERVICE_URL)
    return _user_client


def get_social_client() -> ServiceClient:
    global _social_client
    if _social_client is None:
        _social_client = ServiceClient(SOCIAL_SERVICE_URL)
    return _social_client


async def close_clients() -> None:
    global _user_client, _social_client
    if _user_client is not None:
        await _user_client.aclose()
        _user_client = None
    if _social_client is not None:
        await _social_client.aclose()
        _social_client = None
