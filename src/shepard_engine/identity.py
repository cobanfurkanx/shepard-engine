"""Optional independent identity demo. Never accepts or migrates Supabase credentials."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from shepard_engine.database import connect_database

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


class AuthError(Exception):
    pass


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


class Identity:
    def __init__(self, settings):
        self.settings = settings
        self.url = settings.database_url.get_secret_value()

    def register(self, email, password):
        user = {"id": uuid4(), "email": email.lower(), "password_hash": hasher.hash(password)}
        try:
            with connect_database(self.url) as connection:
                connection.execute(
                    """
                    INSERT INTO engine.users(id, email, password_hash)
                    VALUES (%(id)s, %(email)s, %(password_hash)s)
                """,
                    user,
                )
        except psycopg.errors.UniqueViolation as error:
            raise AuthError("account unavailable") from error
        return {"id": user["id"], "email": user["email"]}

    def login(self, email, password):
        with connect_database(self.url) as connection:
            user = connection.execute(
                "SELECT * FROM engine.users WHERE email=%s", (email.lower(),)
            ).fetchone()
            try:
                hasher.verify(user["password_hash"] if user else dummy_hash, password)
            except (VerificationError, InvalidHashError) as error:
                raise AuthError("invalid credentials") from error
            if not user:
                raise AuthError("invalid credentials")
            if hasher.check_needs_rehash(user["password_hash"]):
                connection.execute(
                    "UPDATE engine.users SET password_hash=%s WHERE id=%s",
                    (hasher.hash(password), user["id"]),
                )
            session = {
                "id": uuid4(),
                "user_id": user["id"],
                "expires_at": datetime.now(UTC) + timedelta(seconds=self.settings.refresh_seconds),
            }
            connection.execute(
                """
                INSERT INTO engine.sessions(id, user_id, expires_at)
                VALUES (%(id)s, %(user_id)s, %(expires_at)s)
            """,
                session,
            )
            return self._issue(connection, session)

    def _issue(self, connection, session):
        now = datetime.now(UTC)
        refresh = secrets.token_urlsafe(48)
        connection.execute(
            "INSERT INTO engine.refresh_tokens(token_hash, session_id) VALUES (%s,%s)",
            (token_hash(refresh), session["id"]),
        )
        expires = min(now + timedelta(seconds=self.settings.access_seconds), session["expires_at"])
        claims = {
            "sub": str(session["user_id"]),
            "sid": str(session["id"]),
            "iat": now,
            "exp": expires,
            "jti": str(uuid4()),
            "type": "access",
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
        }
        access = jwt.encode(claims, self.settings.jwt_secret.get_secret_value(), algorithm="HS256")
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": max(0, int((expires - now).total_seconds())),
        }

    def refresh(self, refresh_token):
        hashed = token_hash(refresh_token)
        issued = None
        with connect_database(self.url) as connection:
            token = connection.execute(
                "SELECT * FROM engine.refresh_tokens WHERE token_hash=%s", (hashed,)
            ).fetchone()
            if token:
                # Consistent lock order: session first, token second. Serializes family rotations.
                session = connection.execute(
                    "SELECT * FROM engine.sessions WHERE id=%s FOR UPDATE", (token["session_id"],)
                ).fetchone()
                token = connection.execute(
                    """
                    SELECT * FROM engine.refresh_tokens WHERE token_hash=%s FOR UPDATE
                """,
                    (hashed,),
                ).fetchone()
                if session and token and not session["revoked"]:
                    if token["consumed"] or session["expires_at"] <= datetime.now(UTC):
                        connection.execute(
                            "UPDATE engine.sessions SET revoked=true WHERE id=%s", (session["id"],)
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE engine.refresh_tokens SET consumed=true WHERE token_hash=%s
                        """,
                            (hashed,),
                        )
                        issued = self._issue(connection, session)
        # Raise AFTER transaction commit: rollback here would undo reuse revocation.
        if not issued:
            raise AuthError("invalid session")
        return issued

    def _claims(self, token):
        try:
            claims = jwt.decode(
                token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["sub", "sid", "iat", "exp", "jti", "type"]},
            )
            if claims["type"] != "access":
                raise AuthError("invalid token")
            # Parse UUIDs before binding to Postgres UUID columns.
            from uuid import UUID

            UUID(claims["sid"])
            UUID(claims["sub"])
            return claims
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise AuthError("invalid token") from error

    def authenticate(self, access_token):
        claims = self._claims(access_token)
        with connect_database(self.url) as connection:
            user = connection.execute(
                """
                SELECT u.id, u.email FROM engine.users u JOIN engine.sessions s ON s.user_id=u.id
                WHERE s.id=%s AND u.id=%s AND NOT s.revoked AND s.expires_at > now()
            """,
                (claims["sid"], claims["sub"]),
            ).fetchone()
        if not user:
            raise AuthError("invalid session")
        return {"id": str(user["id"]), "email": user["email"]}

    def logout(self, access_token):
        claims = self._claims(access_token)
        with connect_database(self.url) as connection:
            connection.execute(
                "UPDATE engine.sessions SET revoked=true WHERE id=%s AND user_id=%s",
                (claims["sid"], claims["sub"]),
            )
