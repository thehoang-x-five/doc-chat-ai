"""
Script to add Google accounts to Cloud Code provider.
Run this to add multiple accounts for automatic rotation.
"""
import asyncio
import logging
from pathlib import Path

from app.services.infrastructure.cloudcode_provider_service import get_cloudcode_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_account_interactive():
    """Add account interactively."""
    print("\n" + "="*60)
    print("  Cloud Code Account Manager")
    print("="*60)
    print("\nThis will add a Google account for FREE Claude/Gemini access.")
    print("You need a Google refresh token from Cloud Code API.\n")
    
    # Get refresh token
    print("Enter your Google refresh token:")
    print("(Get it from: https://accounts.google.com/ → DevTools → Network)")
    refresh_token = input("Refresh token: ").strip()
    
    if not refresh_token:
        print("❌ Refresh token is required!")
        return
    
    # Get optional info
    email = input("Email (optional, will auto-fetch): ").strip()
    name = input("Account name (optional): ").strip()
    
    print("\n⏳ Adding account...")
    
    try:
        manager = get_cloudcode_manager()
        
        # Add account
        account = await manager.add_account_from_refresh_token(
            email=email or "",
            refresh_token=refresh_token,
            name=name or None,
        )
        
        print("\n✅ Account added successfully!")
        print(f"   Email: {account.email}")
        print(f"   ID: {account.id}")
        print(f"   Name: {account.name or 'N/A'}")
        print(f"   Quotas: {len(account.quotas)} models")
        
        if account.quotas:
            print("\n   Model quotas:")
            for model_name, quota in account.quotas.items():
                print(f"     • {model_name}: {quota.percentage:.1f}%")
        
        print(f"\n📁 Saved to: cloudcode_accounts/{account.id}.json")
        
    except Exception as e:
        print(f"\n❌ Failed to add account: {e}")
        logger.exception("Error adding account")


async def list_accounts():
    """List all accounts."""
    print("\n" + "="*60)
    print("  Current Cloud Code Accounts")
    print("="*60 + "\n")
    
    try:
        manager = get_cloudcode_manager()
        count = await manager.load_accounts()
        
        if count == 0:
            print("No accounts found.")
            print("\nAdd accounts using option 1 in the menu.")
            return
        
        accounts = manager.list_accounts()
        
        for i, acc in enumerate(accounts, 1):
            status = "✅ Available" if acc.is_available else "❌ Unavailable"
            print(f"{i}. {acc.name or acc.email} {status}")
            print(f"   Email: {acc.email}")
            print(f"   ID: {acc.id}")
            print(f"   Requests: {acc.total_requests} (Failures: {acc.total_failures})")
            
            if acc.quotas:
                print(f"   Quotas:")
                for model_name, quota in list(acc.quotas.items())[:3]:  # Show first 3
                    print(f"     • {model_name}: {quota.percentage:.1f}%")
                if len(acc.quotas) > 3:
                    print(f"     ... and {len(acc.quotas) - 3} more models")
            print()
        
        print(f"Total: {count} accounts")
        
    except Exception as e:
        print(f"❌ Failed to list accounts: {e}")
        logger.exception("Error listing accounts")


async def remove_account():
    """Remove an account."""
    print("\n" + "="*60)
    print("  Remove Cloud Code Account")
    print("="*60 + "\n")
    
    try:
        manager = get_cloudcode_manager()
        await manager.load_accounts()
        
        accounts = manager.list_accounts()
        if not accounts:
            print("No accounts to remove.")
            return
        
        # Show accounts
        print("Select account to remove:\n")
        for i, acc in enumerate(accounts, 1):
            print(f"{i}. {acc.name or acc.email} ({acc.email})")
        
        choice = input("\nEnter number (or 0 to cancel): ").strip()
        
        try:
            idx = int(choice)
            if idx == 0:
                print("Cancelled.")
                return
            if idx < 1 or idx > len(accounts):
                print("Invalid choice.")
                return
            
            account = accounts[idx - 1]
            confirm = input(f"\n⚠️  Remove {account.email}? (yes/no): ").strip().lower()
            
            if confirm == "yes":
                success = manager.remove_account(account.id)
                if success:
                    print(f"✅ Removed account: {account.email}")
                else:
                    print(f"❌ Failed to remove account")
            else:
                print("Cancelled.")
                
        except ValueError:
            print("Invalid input.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Error removing account")


async def main():
    """Main menu."""
    while True:
        print("\n" + "="*60)
        print("  Cloud Code Multi-Account Manager")
        print("="*60)
        print("\n1. Add new account")
        print("2. List accounts")
        print("3. Remove account")
        print("4. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            await add_account_interactive()
        elif choice == "2":
            await list_accounts()
        elif choice == "3":
            await remove_account()
        elif choice == "4":
            print("\n👋 Goodbye!")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    asyncio.run(main())
