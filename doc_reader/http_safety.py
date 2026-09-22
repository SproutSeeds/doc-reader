"""Small HTTP guards shared by the local app and speech service."""

from urllib.parse import urlsplit

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_UPLOAD_BYTES = 256 * 1024 * 1024


def validate_browser_write(headers) -> None:
    # Native clients have no Origin. Browser requests must originate on the
    # actual app URL, including its port (also works behind Tailscale Serve).
    origin = headers.get("Origin")
    if origin:
        parsed = urlsplit(origin)
        host = headers.get("Host", "").lower()
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host:
            raise PermissionError("Open Doc Reader directly to change settings or submit audio.")
    elif headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        raise PermissionError("Cross-site requests to Doc Reader are not allowed.")


def read_body(handler, *, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    if handler.headers.get("Transfer-Encoding"):
        raise ValueError("Send a Content-Length header; chunked uploads are not supported.")
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Content-Length.") from exc
    if length < 0 or length > limit:
        raise ValueError(f"Request body must be between 0 and {limit // (1024 * 1024)} MB.")
    data = handler.rfile.read(length)
    if len(data) != length:
        raise ValueError("Upload ended before the complete request body arrived.")
    return data
