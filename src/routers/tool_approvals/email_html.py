"""Shared HTML helpers for tool-approval email sends and previews."""
import os
import re

TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://127.0.0.1:4000")


def inject_tracking_pixel(html: str, tracking_id: str) -> str:
    """Inject a 1×1 invisible open-tracking pixel just before </body>."""
    pixel = (
        f'<img src="{TRACKING_BASE_URL}/t/o/{tracking_id}" '
        f'width="1" height="1" style="display:none;border:0;" alt="" />'
    )
    if "</body>" in html.lower():
        return re.sub(r'</body>', f'{pixel}\n</body>', html, count=1, flags=re.IGNORECASE)
    return html + pixel


def strip_html_tags(html: str) -> str:
    """Strip HTML tags and collapse whitespace for a plain-text fallback."""
    text = re.sub(r"<(br\s*/?|/?(p|div|tr|li|h[1-6])[^>]*)>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
