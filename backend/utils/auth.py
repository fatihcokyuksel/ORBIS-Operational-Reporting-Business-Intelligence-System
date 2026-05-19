import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, Response, status

from config.chatbot_config import COOKIE_NAME, COOKIE_SECURE, JWT_SECRET, SESSION_TTL_SECONDS
from utils.database import db


SESSION_REPLACED_MESSAGE = (
    "Bu hesap baska bir cihazda acildigi icin oturumunuz sonlandirildi. "
    "Lutfen tekrar giris yapin."
)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_dumps(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: str, email: str, session_id: str) -> tuple[str, datetime]:
    now = int(time.time())
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
    payload = {
        "userId": user_id,
        "email": email,
        "sessionId": session_id,
        "expiresAt": expires_at.isoformat(),
        "iat": now,
        "exp": int(expires_at.timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64url_encode(_json_dumps(header))}.{_b64url_encode(_json_dumps(payload))}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}", expires_at


def verify_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_decode(encoded_signature), expected_signature):
            return None

        header = json.loads(_b64url_decode(encoded_header))
        if header.get("alg") != "HS256":
            return None

        payload = json.loads(_b64url_decode(encoded_payload))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def set_session_cookie(response: Response, user_id: str, email: str, session_id: str) -> None:
    token, expires_at = create_token(user_id, email, session_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        expires=expires_at,
        max_age=SESSION_TTL_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _resolve_request_token(
    session_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    authorization: str | None = Header(default=None),
) -> str | None:
    token = session_cookie
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    return token


def _resolve_session_payload(token: str | None) -> tuple[dict[str, Any] | None, str]:
    payload = verify_token(token)
    if not payload or not payload.get("userId"):
        return None, "missing"

    session_id = payload.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return None, "missing"

    with db() as connection:
        user = connection.execute(
            'SELECT "activeSessionId" FROM "User" WHERE "id" = ?',
            (payload["userId"],),
        ).fetchone()

    if not user:
        return None, "missing"

    active_session_id = user["activeSessionId"] if "activeSessionId" in user.keys() else None
    if not active_session_id or active_session_id != session_id:
        return None, "replaced"

    return payload, "active"


def get_session_state(
    token: str | None = Depends(_resolve_request_token),
) -> dict[str, Any]:
    payload, reason = _resolve_session_payload(token)
    return {"payload": payload, "reason": reason}


def get_session_payload(
    state: dict[str, Any] = Depends(get_session_state),
) -> dict[str, Any] | None:
    return state.get("payload")


def require_user(
    state: dict[str, Any] = Depends(get_session_state),
) -> dict[str, Any]:
    payload = state.get("payload")
    if not payload or not payload.get("userId"):
        message = SESSION_REPLACED_MESSAGE if state.get("reason") == "replaced" else "Yetkisiz erisim"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": message},
        )
    return payload
