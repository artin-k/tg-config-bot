# Create this as app/list_profiles.py
import asyncio
from app.services.controld import fetch_controld_profiles

async def main():
    print("Connecting to Control D API...")
    profiles = await fetch_controld_profiles()
    
    if not profiles:
        print("❌ No profiles found or failed to connect to the Control D API.")
        print("Please ensure your CONTROLD_API_TOKEN in your .env file is correct.")
        return

    print(f"\n✅ Successfully retrieved {len(profiles)} Profile(s) from Control D:\n")
    print("=" * 60)
    for idx, p in enumerate(profiles, start=1):
        print(f"Plan #{idx}")
        print(f"👤 Name: {p['name']}")
        print(f"🆔 Profile ID (controld_profile_id): {p['id']}")
        print(f"📝 Description: {p['description'] or '-'}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())