from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest

from shepard_engine.identity import AuthError, Identity, token_hash

pytestmark = pytest.mark.integration


def test_rotation_reuse_revokes_access_and_new_refresh(integration_settings):
    identity = Identity(integration_settings)
    user = identity.register("test@example.com", "strong-password-123")
    first = identity.login("test@example.com", "strong-password-123")
    assert identity.authenticate(first["access_token"])["id"] == str(user["id"])
    second = identity.refresh(first["refresh_token"])
    assert second["refresh_token"] != first["refresh_token"]
    assert token_hash(first["refresh_token"]) != first["refresh_token"]
    with pytest.raises(AuthError):
        identity.refresh(first["refresh_token"])
    for token in (first["access_token"], second["access_token"]):
        with pytest.raises(AuthError):
            identity.authenticate(token)
    with pytest.raises(AuthError):
        identity.refresh(second["refresh_token"])


def test_concurrent_refresh_cannot_create_two_valid_sessions(integration_settings):
    identity = Identity(integration_settings)
    identity.register("test@example.com", "strong-password-123")
    first = identity.login("test@example.com", "strong-password-123")

    def rotate():
        try:
            return identity.refresh(first["refresh_token"])
        except AuthError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: rotate(), range(2)))
    assert sum(result is not None for result in results) == 1
    issued = next(result for result in results if result)
    with pytest.raises(AuthError):
        identity.authenticate(issued["access_token"])


def test_invalid_credentials_tokens_and_logout(integration_settings):
    identity = Identity(integration_settings)
    identity.register("test@example.com", "strong-password-123")
    with pytest.raises(AuthError):
        identity.register("test@example.com", "strong-password-123")
    for email, password in [("missing@example.com", "wrong"), ("test@example.com", "wrong")]:
        with pytest.raises(AuthError):
            identity.login(email, password)
    with pytest.raises(AuthError):
        identity.refresh("not-a-token")
    with pytest.raises(AuthError):
        identity.authenticate("not-a-jwt")
    first = identity.login("test@example.com", "strong-password-123")
    claims = jwt.decode(first["access_token"], options={"verify_signature": False})
    claims["aud"] = "wrong"
    signed = jwt.encode(
        claims, integration_settings.jwt_secret.get_secret_value(), algorithm="HS256"
    )
    with pytest.raises(AuthError):
        identity.authenticate(signed)
    identity.logout(first["access_token"])
    with pytest.raises(AuthError):
        identity.refresh(first["refresh_token"])
