"""Send empty status pings; never attach application data or provider errors."""

import re
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def validate_ping_url(url):
    if not re.fullmatch(
        r"https://hc-ping\.com/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", url
    ):
        raise ValueError("Configure a private HTTPS Healthchecks UUID URL.")


def ping(url, state="success"):
    validate_ping_url(url)
    if state not in {"start", "success", "fail"}:
        raise ValueError("Unsupported monitor state.")
    suffix = "" if state == "success" else "/" + state
    request = Request(url + suffix, data=b"", method="POST")
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        # Unknown/rate-limited checks can return HTTP 200 with a non-OK body.
        if response.status != 200 or response.read(128).strip() != b"OK":
            raise ValueError("Monitoring service did not acknowledge the status ping.")
