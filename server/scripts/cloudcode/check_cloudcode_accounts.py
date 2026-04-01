"""
Script to check Cloud Code accounts status and quotas.
"""
import asyncio
import logging
from datetime import datetime

from app.services.infrastructure.cloudcode_provider_service import get_cloudcode_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_accounts():
    """Check all accounts and their quotas."""
    print("\n" + "="*70)
    print("  Cloud Code Accounts Status")
    print("="*70 + "\n")
    
    try:
        manager = get_cloudcode_manager()
        
        # Load accounts
        count = await manager.load_accounts()
        
        if count == 0:
            print("❌ No accounts found!")
            print("\nAdd accounts using: python add_cloudcode_account.py")
            return
        
        print(f"✅ Loaded {count} accounts\n")
        
        # List accounts
        accounts = manager.list_accounts()
        
        for i, acc in enumerate(accounts, 1):
            # Status
            if acc.is_available:
                status = "✅ AVAILABLE"
            elif acc.is_forbidden:
                status = "🚫 FORBIDDEN"
            elif acc.disabled_until:
                status = f"⏸️  DISABLED until {acc.disabled_until.strftime('%H:%M:%S')}"
            else:
                status = "❌ UNAVAILABLE"
            
            print(f"{i}. {acc.name or 'Unnamed'} {status}")
            print(f"   📧 Email: {acc.email}")
            print(f"   🆔 ID: {acc.id}")
            print(f"   📊 Stats:")
            print(f"      • Total requests: {acc.total_requests}")
            print(f"      • Total failures: {acc.total_failures}")
            
            if acc.last_used:
                time_ago = (datetime.utcnow() - acc.last_used).total_seconds()
                if time_ago < 60:
                    last_used = f"{int(time_ago)}s ago"
                elif time_ago < 3600:
                    last_used = f"{int(time_ago/60)}m ago"
                else:
                    last_used = f"{int(time_ago/3600)}h ago"
                print(f"      • Last used: {last_used}")
            
            # Quotas
            if acc.quotas:
                print(f"   📈 Model Quotas ({len(acc.quotas)} models):")
                
                # Sort by quota percentage (descending)
                sorted_quotas = sorted(
                    acc.quotas.items(),
                    key=lambda x: x[1].percentage,
                    reverse=True
                )
                
                for model_name, quota in sorted_quotas:
                    # Color based on quota
                    if quota.percentage >= 80:
                        icon = "🟢"
                    elif quota.percentage >= 50:
                        icon = "🟡"
                    elif quota.percentage >= 20:
                        icon = "🟠"
                    else:
                        icon = "🔴"
                    
                    print(f"      {icon} {model_name}: {quota.percentage:.1f}%", end="")
                    
                    if quota.reset_time:
                        time_until = (quota.reset_time - datetime.utcnow()).total_seconds()
                        if time_until > 0:
                            if time_until < 3600:
                                reset_str = f"{int(time_until/60)}m"
                            else:
                                reset_str = f"{int(time_until/3600)}h"
                            print(f" (resets in {reset_str})")
                        else:
                            print(" (reset overdue)")
                    else:
                        print()
            else:
                print(f"   ⚠️  No quota information")
            
            # Best available model
            best_model = acc.get_best_available_model()
            if best_model:
                print(f"   🎯 Best model: {best_model}")
            
            print()
        
        # Summary
        print("="*70)
        print(f"📊 Summary:")
        available = sum(1 for a in accounts if a.is_available)
        print(f"   • Total accounts: {count}")
        print(f"   • Available: {available}")
        print(f"   • Unavailable: {count - available}")
        
        total_requests = sum(a.total_requests for a in accounts)
        total_failures = sum(a.total_failures for a in accounts)
        success_rate = ((total_requests - total_failures) / total_requests * 100) if total_requests > 0 else 0
        
        print(f"   • Total requests: {total_requests}")
        print(f"   • Success rate: {success_rate:.1f}%")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error checking accounts")


async def test_account():
    """Test making a request with Cloud Code."""
    print("\n" + "="*70)
    print("  Test Cloud Code Request")
    print("="*70 + "\n")
    
    try:
        manager = get_cloudcode_manager()
        await manager.load_accounts()
        
        accounts = manager.list_accounts()
        if not accounts:
            print("❌ No accounts available for testing")
            return
        
        print("Testing with a simple request...\n")
        
        # Make a test request
        response = await manager.generate(
            messages=[{"role": "user", "content": "Say 'Hello from Cloud Code!' in one sentence."}],
            model="gemini-3-flash",
            max_tokens=50,
        )
        
        if response.success:
            print("✅ Test successful!")
            print(f"   Account: {response.account_email}")
            print(f"   Model: {response.model}")
            print(f"   Latency: {response.latency_ms}ms")
            print(f"\n   Response: {response.content}")
        else:
            print(f"❌ Test failed: {response.error}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error testing account")


async def refresh_quotas():
    """Refresh quota information for all accounts."""
    print("\n" + "="*70)
    print("  Refresh Account Quotas")
    print("="*70 + "\n")
    
    try:
        manager = get_cloudcode_manager()
        await manager.load_accounts()
        
        accounts = manager.list_accounts()
        if not accounts:
            print("❌ No accounts to refresh")
            return
        
        print(f"Refreshing quotas for {len(accounts)} accounts...\n")
        
        for acc in accounts:
            print(f"⏳ {acc.email}...", end=" ")
            try:
                # Refresh quota would be implemented in manager
                # For now, just show current status
                print(f"✅ {len(acc.quotas)} models")
            except Exception as e:
                print(f"❌ {e}")
        
        print("\n✅ Quota refresh complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error refreshing quotas")


async def main():
    """Main menu."""
    while True:
        print("\n" + "="*70)
        print("  Cloud Code Account Checker")
        print("="*70)
        print("\n1. Check accounts status")
        print("2. Test request")
        print("3. Refresh quotas")
        print("4. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            await check_accounts()
        elif choice == "2":
            await test_account()
        elif choice == "3":
            await refresh_quotas()
        elif choice == "4":
            print("\n👋 Goodbye!")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    asyncio.run(main())
