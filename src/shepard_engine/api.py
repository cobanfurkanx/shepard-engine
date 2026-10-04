import asyncio
import time
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from redis import Redis
from redis.exceptions import RedisError

from shepard_engine.cache import MarketCache, allow_request
from shepard_engine.database import connect_database
from shepard_engine.identity import AuthError, Identity
from shepard_engine.reporting import market_report, report_boundary
from shepard_engine.settings import get_settings


class Credentials(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=128)


bearer = HTTPBearer(auto_error=False)


def create_app(settings=None, *, redis=None):
    settings = settings or get_settings()
    owned = redis is None
    redis = (
        redis
        if redis is not None
        else Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    )
    cache = MarketCache(redis)
    identity = Identity(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owned:
            redis.close()

    application = FastAPI(title="Shepard Engine", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.middleware("http")
    async def boundary(request: Request, call_next):
        path = request.url.path
        if path.startswith("/v1/auth") and not settings.identity_enabled:
            return JSONResponse({"detail": "identity module disabled"}, status_code=404)
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdigit() or request.headers.get("transfer-encoding"):
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            if int(length) > 4096:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        if path.startswith("/v1/"):
            auth = path.startswith("/v1/auth/")
            key = f"{'auth' if auth else 'market'}:{request.client.host}"
            try:
                allowed = await asyncio.to_thread(allow_request, redis, key, 10 if auth else 60, 60)
            except RedisError:
                return JSONResponse({"detail": "service unavailable"}, status_code=503)
            if not allowed:
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse(
            {"detail": "invalid credentials or session"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def unavailable(request, error):
        return JSONResponse({"detail": "service unavailable"}, status_code=503)

    application.add_exception_handler(psycopg.Error, unavailable)
    application.add_exception_handler(RedisError, unavailable)

    def access(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if not credentials:
            raise HTTPException(
                401, "authentication required", headers={"WWW-Authenticate": "Bearer"}
            )
        return credentials.credentials

    @application.get("/health/live")
    def live():
        return {"status": "ok"}

    @application.get("/health/ready")
    def ready():
        redis.ping()
        with connect_database(settings.database_url.get_secret_value()) as connection:
            connection.execute("SELECT 1")
        return {"status": "ready"}

    @application.get("/health/market")
    def market_health():
        if not redis.get("engine:ingestion_alive") or not redis.get("engine:worker_alive"):
            raise HTTPException(503, "market pipeline unavailable")
        return {"status": "ready"}

    @application.get("/v1/market/ticker/{symbol}")
    def ticker(symbol: str):
        if symbol not in settings.symbol_set:
            raise HTTPException(404, "unknown symbol")
        value = cache.ticker(symbol)
        offset = int(redis.get("engine:exchange_clock_offset_ms") or 0)
        age = int(time.time() * 1000) + offset - value["event_ms"] if value else 0
        if not value or age > 60000 or age < -5000:
            raise HTTPException(503, "market data stale or unavailable")
        return value

    @application.get("/v1/market/top-coins")
    def top_coins():
        with connect_database(settings.database_url.get_secret_value()) as connection:
            try:
                offset = int(redis.get("engine:exchange_clock_offset_ms") or 0)
                end_ms = report_boundary(
                    connection, settings.symbol_set, int(time.time() * 1000) + offset
                )
            except ValueError as error:
                raise HTTPException(503, str(error)) from error
            items = market_report(connection, end_ms, settings.symbol_set)
        return {"items": items, "as_of_ms": end_ms, "interval": "15m", "window_hours": 24}

    @application.post("/v1/auth/register", status_code=201)
    def register(body: Credentials):
        return identity.register(str(body.email), body.password)

    @application.post("/v1/auth/login")
    def login(body: Credentials):
        # Per-account limiting also applies across distinct IP addresses.
        if not allow_request(redis, f"account:{str(body.email).lower()}", 10, 300):
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "300"})
        return identity.login(str(body.email), body.password)

    @application.post("/v1/auth/refresh")
    def refresh(body: RefreshBody):
        return identity.refresh(body.refresh_token)

    @application.get("/v1/auth/me")
    def me(token: str = Depends(access)):
        return identity.authenticate(token)

    @application.post("/v1/auth/logout", status_code=204)
    def logout(token: str = Depends(access)):
        identity.logout(token)

    return application


app = create_app()
