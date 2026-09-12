"""Fetcher transport behaviour, especially response decoding.

Regression cover for a bug where the fetcher hard-coded
``Accept-Encoding: gzip, deflate, br`` without the brotli decoder installed.
Every brotli-serving origin (anything behind Cloudflare) then came back as raw
compressed bytes, so the parsed page had no title and no headings, and text
extraction tokenized binary noise into nonsense "keywords".
"""
import gzip

import brotli
import httpx
import pytest
import respx
from bs4 import BeautifulSoup

from app.seo import fetcher

HTML = "<!doctype html><html><head><title>Decoded Fine</title></head><body><h1>Real Heading</h1></body></html>"


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "encoding, compress",
    [
        ("br", brotli.compress),
        ("gzip", gzip.compress),
        (None, lambda raw: raw),
    ],
)
async def test_compressed_responses_are_decoded(encoding, compress):
    headers = {"content-type": "text/html"}
    if encoding:
        headers["content-encoding"] = encoding
    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200, content=compress(HTML.encode()), headers=headers
        )
    )

    result = await fetcher.fetch("https://example.com")

    assert result.ok
    assert "<title>" in result.text.lower(), f"{encoding} response was not decoded"
    soup = BeautifulSoup(result.content, "lxml")
    assert soup.find("title").get_text() == "Decoded Fine"
    assert soup.find("h1").get_text() == "Real Heading"


@pytest.mark.asyncio
async def test_accept_encoding_only_claims_decodable_codecs():
    """The header must never promise an encoding httpx cannot decode.

    Asserted against httpx's own default rather than a literal list, because the
    set depends on which decoder packages are installed.
    """
    sent: dict[str, str] = {}

    async def capture(request: httpx.Request) -> httpx.Response:
        sent.update(request.headers)
        return httpx.Response(200, html=HTML)

    with respx.mock:
        respx.get("https://example.com").mock(side_effect=capture)
        await fetcher.fetch("https://example.com")

    expected = httpx.Client().headers["accept-encoding"]
    assert sent["accept-encoding"] == expected
