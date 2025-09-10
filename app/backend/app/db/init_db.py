import asyncio
from app.db.session import engine, Base
from app import models  # noqa: F401  (imports all models so metadata is populated)

async def _init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def main():
    asyncio.run(_init())

if __name__ == "__main__":
    main()
