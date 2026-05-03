import hashlib


def query_hash(*parts: str) -> str:
    """Return short sha256 hash of joined query parts.

    Used in logs instead of raw user input to satisfy the "never log raw
    query input" invariant from GOALS.md.
    """
    joined = " ".join(p for p in parts if p)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
