"""Create ignored local credentials without overwriting existing configuration."""

import secrets
from pathlib import Path

target = Path(".env.local")
password, redis_password = secrets.token_hex(24), secrets.token_hex(24)
with target.open("x", encoding="utf-8") as stream:
    stream.write(f"POSTGRES_PASSWORD={password}\nREDIS_PASSWORD={redis_password}\n")
    stream.write(f"ENGINE_DATABASE_URL=postgresql://engine:{password}@localhost:55432/engine\n")
    stream.write(f"ENGINE_REDIS_URL=redis://:{redis_password}@localhost:56379/0\n")
    stream.write(f"ENGINE_JWT_SECRET={secrets.token_hex(32)}\nENGINE_IDENTITY_ENABLED=false\n")
print("Local configuration created. Identity disabled.")
