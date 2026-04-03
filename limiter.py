from slowapi import Limiter


def get_client_ip(request):
    """Get client IP address, respecting proxy headers when available."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host


limiter = Limiter(key_func=get_client_ip)
