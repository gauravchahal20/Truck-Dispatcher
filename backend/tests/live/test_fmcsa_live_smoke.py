import pytest
import httpx


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_socrata_az4n_8mr2_census_query():
    """Live smoke test: az4n-8mr2 (Company Census File)."""
    url = "https://data.transportation.gov/resource/az4n-8mr2.json?$where=phy_state='TX' AND status_code='A'&$limit=2"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "dot_number" in data[0]
        assert "legal_name" in data[0]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_socrata_kjg3_diqy_sms_query():
    """Live smoke test: kjg3-diqy (SMS Input - Motor Carrier Census Information)."""
    url = "https://data.transportation.gov/resource/kjg3-diqy.json?$limit=2"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "dot_number" in data[0]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_socrata_wb4f_neki_revocations_query():
    """Live smoke test: wb4f-neki (Motus RevokeSuspend - All With History)."""
    url = "https://data.transportation.gov/resource/wb4f-neki.json?$limit=2"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "usdot_number" in data[0] or "docket_number" in data[0]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_socrata_e67p_xyd5_active_revocations_query():
    """Live smoke test: e67p-xyd5 (Motus RevokeSuspend)."""
    url = "https://data.transportation.gov/resource/e67p-xyd5.json?$limit=2"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "usdot_number" in data[0] or "docket_number" in data[0]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_socrata_p2mt_9ige_oos_orders_query():
    """Live smoke test: p2mt-9ige (OUT OF SERVICE ORDERS)."""
    url = "https://data.transportation.gov/resource/p2mt-9ige.json?$limit=2"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "dot_number" in data[0]
