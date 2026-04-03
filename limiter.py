from slowapi import Limiter


def get_client_ip(request):
    """Get client IP address.

    Uses request.client.host (actual TCP peer) as the authoritative source.
    X-Forwarded-For is only used when behind a known trusted proxy.
    """
    # Default to the actual TCP peer address (cannot be spoofed)
    client_host = request.client.host if request.client else "unknown"

    # Only trust proxy headers when behind a known trusted proxy
    trusted_proxies = getattr(request.app.state, "trusted_proxies", None) or set()
    if isinstance(trusted_proxies, str):
        trusted_proxies = {p.strip() for p in trusted_proxies.split(",") if p.strip()}
    elif not isinstance(trusted_proxies, set):
        trusted_proxies = set(trusted_proxies)

    if trusted_proxies and client_host in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return client_host


limiter = Limiter(key_func=get_client_ip)
