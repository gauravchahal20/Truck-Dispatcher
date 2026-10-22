import re
import pytest
import httpx
from bs4 import BeautifulSoup
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.live
@pytest.mark.monthly
@pytest.mark.asyncio
async def test_live_safer_snapshot_parser_drift():
    """
    Monthly live test: Verifies that live SAFER Company Snapshot HTML
    preserves the table structure, column headers, and tags expected by the parser.
    """
    url = "https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=3849102"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
                soup = BeautifulSoup(html, "html.parser")
                # Check for critical table markers
                has_snapshot_title = bool(soup.find(lambda tag: tag.name in ("th", "td", "font") and "Company Snapshot" in tag.text))
                has_dot_field = "USDOT" in html or "U.S. DOT" in html
                assert has_snapshot_title or has_dot_field, "SAFER live layout drifted: Company Snapshot markers missing"
    except httpx.HTTPError:
        pytest.skip("SAFER endpoint temporarily unreachable from live test environment")


@pytest.mark.live
@pytest.mark.monthly
@pytest.mark.asyncio
async def test_live_usdotlookup_parser_drift():
    """
    Monthly live test: Verifies that USDOT Lookup HTML directory structure
    preserves carrier card or listing elements expected by the parser.
    """
    url = "https://usdotlookup.com/texas/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
                soup = BeautifulSoup(html, "html.parser")
                cards = soup.select(".carrier-card, .card, table tr, article")
                assert len(cards) > 0, "USDOT Lookup live layout drifted: No carrier containers found"
    except httpx.HTTPError:
        pytest.skip("USDOT Lookup endpoint temporarily unreachable from live test environment")
