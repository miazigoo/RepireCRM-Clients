import secrets


def token(bytes_count: int = 48) -> str:
    return secrets.token_urlsafe(bytes_count)


print(f"CLIENT_PORTAL_SECRET_KEY={token(64)}")
print(f"CLIENT_PORTAL_SYNC_API_KEY={token(48)}")
print(f"POSTGRES_PASSWORD={token(32)}")
