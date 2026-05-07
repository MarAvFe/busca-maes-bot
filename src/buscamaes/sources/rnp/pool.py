import logging

from ...settings import get_settings
from .client import RNPClient, RNPUnavailable
from .models import VehicleResult

logger = logging.getLogger(__name__)

_rnp_pool_instance: "RNPPool | None" = None


class RNPPool:
    """Round-robin pool of RNPClient instances, one per account."""

    def __init__(self, accounts: list[tuple[str, str]], base_url: str, timeout: int) -> None:
        self._clients = [
            RNPClient(email=email, password=password, base_url=base_url, timeout=timeout)
            for email, password in accounts
        ]
        self._index = 0
        logger.info("RNPPool initialized with %d account(s)", len(self._clients))

    async def query_plate(self, class_code: str, car_number: str) -> VehicleResult:
        if not self._clients:
            raise RNPUnavailable("No RNP accounts configured")
        n = len(self._clients)
        start = self._index
        for i in range(n):
            client = self._clients[(start + i) % n]
            try:
                result = await client.query_plate(class_code, car_number)
                self._index = (start + i + 1) % n
                return result
            except RNPUnavailable:
                logger.debug("Account %d unavailable, trying next", (start + i) % n)
                continue
        raise RNPUnavailable("All RNP accounts are currently unavailable")


def get_rnp_pool() -> RNPPool:
    global _rnp_pool_instance
    if _rnp_pool_instance is None:
        s = get_settings()
        _rnp_pool_instance = RNPPool(s.rnp_accounts, s.rnp_base_url, s.rnp_timeout)
    return _rnp_pool_instance


def reset_rnp_pool() -> None:
    """Reset the pool singleton. Only for testing."""
    global _rnp_pool_instance
    _rnp_pool_instance = None
