import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        params = {
            "$limit": 5,
            "$where": "status_code='A' and phy_state='TX' and power_units in('2', '3', '4', '5', '6', '7', '8', '9', '10')",
            "$order": "add_date DESC"
        }
        r = await client.get("https://data.transportation.gov/resource/az4n-8mr2.json", params=params)
        print("Status with in(...):", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("Records count:", len(data))
            for i, rec in enumerate(data):
                print(f"[{i+1}] USDOT: {rec.get('dot_number')} | MC: {rec.get('docket1')} | Name: {rec.get('legal_name')} | Phone: {rec.get('phone')} | City: {rec.get('phy_city')}, {rec.get('phy_state')} | Fleet: {rec.get('power_units')} | Class: {rec.get('classdef')}")
        else:
            print("Error:", r.text[:300])

if __name__ == "__main__":
    asyncio.run(test())
