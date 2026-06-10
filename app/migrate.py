# Create this as app/migrate.py
import asyncio
import structlog
from sqlalchemy import text
from app.database import engine

logger = structlog.get_logger(__name__)

async def run_migrations():
    print("Connecting to database and running table updates...")
    
    async with engine.begin() as conn:
        # 1. Add column to 'plans' table
        try:
            await conn.execute(text("ALTER TABLE plans ADD COLUMN IF NOT EXISTS controld_profile_id VARCHAR(64);"))
            print("✅ Successfully updated 'plans' table with 'controld_profile_id' column.")
        except Exception as e:
            print(f"❌ Error updating 'plans' table: {e}")

        # 2. Add column to 'vpn_services' table
        try:
            await conn.execute(text("ALTER TABLE vpn_services ADD COLUMN IF NOT EXISTS controld_device_id VARCHAR(128);"))
            print("✅ Successfully updated 'vpn_services' table with 'controld_device_id' column.")
        except Exception as e:
            print(f"❌ Error updating 'vpn_services' table: {e}")

    await engine.dispose()
    print("Database update complete.")

if __name__ == "__main__":
    asyncio.run(run_migrations())