import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeWebhookURLError(ValueError):
    """Raised when a webhook URL points at a disallowed destination."""


def ensure_safe_webhook_url(url: str) -> None:
    """Reject webhook URLs that resolve to internal/private infrastructure.

    Called both at request time (schema validation) and again right before
    delivery, since the hostname's resolved IP can change between the two
    (DNS rebinding) and only checking once would leave an SSRF window.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise UnsafeWebhookURLError("Webhook URL must use http or https")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeWebhookURLError("Webhook URL must include a hostname")

    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeWebhookURLError(
            "Webhook URL hostname could not be resolved"
        ) from exc

    for *_rest, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeWebhookURLError(
                f"Webhook URL resolves to a disallowed address: {ip}"
            )
