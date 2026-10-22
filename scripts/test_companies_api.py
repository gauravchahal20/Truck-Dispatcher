import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.database import AsyncSessionLocal
from app.api.routes_companies import list_companies
from app.schemas.schemas import CompanyResponse

async def main():
    async with AsyncSessionLocal() as session:
        try:
            res = await list_companies(limit=100, session=session)
            print(f"Successfully retrieved {len(res)} companies via list_companies")
            for i, comp in enumerate(res):
                validated = CompanyResponse.model_validate(comp)
            print("Successfully validated all 100 companies with CompanyResponse schema!")
        except Exception as e:
            print(f"Error validating company {i}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
