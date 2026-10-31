from __future__ import annotations

import hashlib
import hmac
import time


PBKDF2_ITERATIONS = 600_000


def verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    if not salt_hex or not expected_hex:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    ).hex()
    return hmac.compare_digest(actual, expected_hex)


def make_session(secret: str, lifetime_minutes: int) -> str:
    expiry = str(int(time.time()) + lifetime_minutes * 60)
    signature = hmac.new(secret.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return expiry + "." + signature


def valid_session(token: str | None, secret: str) -> bool:
    if not token or "." not in token or not secret:
        return False
    expiry, signature = token.split(".", 1)
    if not expiry.isdigit() or int(expiry) < int(time.time()):
        return False
    expected = hmac.new(secret.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)