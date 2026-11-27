"""
Lab 5 — Forwarding a request to a backend service.

Owner: Youssef. This is the minimal version Douae needs for the static
gateway (Problem 1, 5b). Youssef completes it:
  - full hop-by-hop header list (request and response),
  - X-Forwarded-For / X-Forwarded-Proto / X-Forwarded-Host,
  - connection refused -> 502, timeout -> 504 (contract §5.3),
  - tests/test_proxy.py.
"""

import httpx
from fastapi import Request
from fastapi.responses import Response

# Headers that describe one connection, not the message: never copied as-is.
_REQUEST_SKIP = {"host", "content-length"}
_RESPONSE_SKIP = {"content-length", "transfer-encoding", "connection", "content-encoding"}


async def forward(request: Request, base_url: str, client: httpx.AsyncClient) -> Response:
    """Send the same method, path, query, headers and body to base_url and return its answer."""
    url = base_url + request.url.path
    if request.url.query:
        url += "?" + request.url.query

    headers = [
        (name, value)
        for name, value in request.headers.items()
        if name.lower() not in _REQUEST_SKIP
    ]

    upstream = await client.request(
        request.method,
        url,
        headers=headers,
        content=await request.body(),
    )

    response = Response(content=upstream.content, status_code=upstream.status_code)
    for name, value in upstream.headers.multi_items():
        if name.lower() not in _RESPONSE_SKIP:
            response.headers.append(name, value)
    return response
