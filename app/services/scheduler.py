# Open app/services/scheduler.py
import asyncio
from datetime import datetime, timezone
import structlog
from sqlalchemy import select

from app.database import async_session_maker
from app.models import VPNService, VPNServiceStatus, Plan
from app.config import get_settings
# --- FIXED: Import the OOP client wrapper instead of standalone functions ---
from app.services.controld import ControlDService
# ----------------------------------------------------------------------------

logger = structlog.get_logger(__name__)


async def cleanup_expired_dns_services() -> None:
    """
    Finds all expired DNS services, calls the Control D API to delete the device,
    and updates their status to 'expired' inside the PostgreSQL database.
    """
    now = datetime.now(timezone.utc)
    settings = get_settings()
    
    # Instantiate the proxy-aware OOP client
    cd_service = ControlDService(settings)
    
    async with async_session_maker() as session:
        # 1. Query active DNS configurations that have crossed their expiration time
        stmt = (
            select(VPNService)
            .where(
                VPNService.status == VPNServiceStatus.ACTIVE.value,
                VPNService.expire_at < now
            )
        )
        result = await session.execute(stmt)
        expired_services = result.scalars().all()

        if not expired_services:
            return

        logger.info("checking_expired_dns_services", count=len(expired_services))

        for service in expired_services:
            # 2. If the subscription has an associated Control D Device ID, request deletion
            if service.controld_device_id:
                logger.info("deleting_controld_device", service_id=service.id, device_id=service.controld_device_id)
                
                # --- FIXED: Use the OOP client method to delete the device ---
                success = await cd_service.delete_device(service.controld_device_id)
                # -------------------------------------------------------------
                if success:
                    logger.info("controld_device_deleted_successfully", service_id=service.id)
                else:
                    logger.warning("failed_to_delete_controld_device", service_id=service.id)
            
            # 3. Mark the status as EXPIRED locally so we don't query it again
            service.status = VPNServiceStatus.EXPIRED.value
        
        await session.commit()


async def sync_plans_with_controld(session) -> None:
    """
    Synchronizes your Control D dashboard Profiles with local Plans in PostgreSQL.
    """
    settings = get_settings()
    
    # Instantiate the proxy-aware OOP client
    cd_service = ControlDService(settings)
    
    # --- FIXED: Use the OOP client method to retrieve profiles ---
    profiles = await cd_service.fetch_controld_profiles()
    # --------------------------------------------------------------
    if not profiles:
        logger.warning("no_controld_profiles_found_or_sync_failed")
        return

    logger.info("syncing_controld_profiles_to_database", count=len(profiles))

    for profile in profiles:
        profile_id = profile["id"]
        profile_name = profile["name"]
        profile_desc = profile["description"] or "سرویس دی‌ان‌اس اختصاصی"

        # Check if this profile is already registered as a plan in our DB
        stmt = select(Plan).where(Plan.controld_profile_id == profile_id)
        result = await session.execute(stmt)
        
        # Strictly use .first() to prevent multiple-row crashes
        existing_plan = result.scalars().first()

        if existing_plan is None:
            # Create a brand new plan with default prices/durations
            new_plan = Plan(
                title=profile_name,
                description=profile_desc,
                duration_hours=720,         # Default: 30 days = 720 hours
                volume_gb=0,                # DNS has no volume limit
                price=50000,                # Default price (Toman) - edit this later in Admin Panel
                is_active=True,
                sort_order=0,
                controld_profile_id=profile_id
            )
            session.add(new_plan)
            logger.info("synced_new_dns_plan", title=profile_name, id=profile_id)
        else:
            # Update title and description if they were modified on the Control D dashboard
            existing_plan.title = profile_name
            if profile["description"]:
                existing_plan.description = profile_desc
                
    await session.commit()


async def expiration_scheduler_loop(interval_seconds: int = 3600) -> None:
    """
    Background loop checking for expired subscription parameters once every hour.
    """
    logger.info("starting_expiration_scheduler_loop", interval_seconds=interval_seconds)
    while True:
        try:
            await cleanup_expired_dns_services()
        except Exception as e:
            logger.error("expiration_scheduler_loop_error", error=str(e))
        
        await asyncio.sleep(interval_seconds)