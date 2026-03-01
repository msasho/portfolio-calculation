import time
import logging
import requests

logger = logging.getLogger("portfolio")


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.timestamps: list[float] = []

    def wait(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < self.period]
        if len(self.timestamps) >= self.max_calls:
            sleep_until = self.timestamps[0] + self.period
            sleep_time = sleep_until - now
            if sleep_time > 0:
                logger.debug(f"Rate limit: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


def retry_request(func, max_retries=3, backoff_factor=1.0):
    for attempt in range(max_retries):
        try:
            return func()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff_factor * (2 ** attempt)
            logger.warning(f"Request failed ({e}), retrying in {wait:.1f}s...")
            time.sleep(wait)


def json_rpc_request(url: str, method: str, params: list, rate_limiter: RateLimiter = None) -> dict:
    if rate_limiter:
        rate_limiter.wait()

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    def _do():
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    data = retry_request(_do)
    if "error" in data:
        raise RuntimeError(f"RPC error ({method}): {data['error']}")
    return data.get("result")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("portfolio")
