"""
DEPRECATED: This script is no longer needed.

The encrypted_api_key column has been removed from the credentials table.
All credentials now use the encrypted_data column with JSON structure.

This script was used to migrate credentials from the legacy format 
(encrypted_api_key only) to the new flexible format (encrypted_data with JSON).

If you need to run this migration (for an older database), ensure you:
1. Have the encrypted_api_key column still in your database
2. Run this script BEFORE running the b2c3d4e5f6a7 migration
   (which removes the encrypted_api_key column)

For new installations, this script is not needed.
"""
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db.database import SessionLocal
from src.db.models import Credential
from src.routers.credentials.encryption import (
    decrypt_api_key, 
    encrypt_credential_data,
    decrypt_credential_data
)

load_dotenv()


def migrate_credentials_to_flexible_format(dry_run: bool = False, force: bool = False):
    """
    Migrate all credentials from legacy format to flexible JSON format.
    
    Args:
        dry_run: If True, only shows what would be migrated without making changes
        force: If True, re-migrate credentials even if encrypted_data already exists
    """
    db = SessionLocal()
    
    try:
        # Get all credentials
        credentials = db.query(Credential).all()
        
        if not credentials:
            print("No credentials found in database.")
            return
        
        print(f"Found {len(credentials)} credential(s) to process.")
        
        # Count credentials needing migration
        needs_migration = []
        already_migrated = []
        no_legacy_data = []
        
        for cred in credentials:
            if cred.encrypted_data and not force:
                already_migrated.append(cred)
            elif cred.encrypted_api_key:
                needs_migration.append(cred)
            else:
                no_legacy_data.append(cred)
        
        print(f"\nBreakdown:")
        print(f"  - Needs migration: {len(needs_migration)}")
        print(f"  - Already migrated: {len(already_migrated)}")
        print(f"  - No legacy data: {len(no_legacy_data)}")
        
        if not needs_migration and not force:
            print("\n✓ All credentials are already migrated.")
            if already_migrated and not force:
                print("   Use --force to re-migrate all credentials.")
            return
        
        # If force, also include already_migrated credentials
        if force and already_migrated:
            needs_migration.extend(already_migrated)
            print(f"\n--force flag set, will migrate {len(needs_migration)} credential(s).")
        
        if dry_run:
            print("\n[DRY RUN] Would migrate the following credentials:")
        else:
            print("\nMigrating credentials...")
        
        success_count = 0
        error_count = 0
        
        for cred in needs_migration:
            try:
                # Decrypt the legacy API key
                decrypted_key = decrypt_api_key(cred.encrypted_api_key)
                
                # Create new JSON structure
                credential_data = {"api_key": decrypted_key}
                
                if dry_run:
                    # Verify the structure would work
                    encrypted = encrypt_credential_data(credential_data)
                    decrypted = decrypt_credential_data(encrypted)
                    
                    if decrypted.get("api_key") == decrypted_key:
                        print(f"  ✓ Credential ID {cred.id} ({cred.service_name}): OK")
                        success_count += 1
                    else:
                        print(f"  ✗ Credential ID {cred.id} ({cred.service_name}): Verification failed")
                        error_count += 1
                else:
                    # Encrypt in new format
                    encrypted_data = encrypt_credential_data(credential_data)
                    
                    # Update the credential
                    cred.encrypted_data = encrypted_data
                    cred.credential_type = "api_key"
                    # Keep encrypted_api_key for backward compatibility
                    
                    db.add(cred)
                    success_count += 1
                    print(f"  ✓ Migrated credential ID {cred.id} ({cred.service_name})")
                    
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error processing credential ID {cred.id} ({cred.service_name}): {str(e)}")
        
        if not dry_run:
            if success_count > 0:
                db.commit()
                print(f"\n✓ Successfully migrated {success_count} credential(s).")
            else:
                db.rollback()
                print("\n✗ No credentials were migrated. Rolling back changes.")
        
        if error_count > 0:
            print(f"\n⚠ {error_count} credential(s) could not be processed.")
            if not dry_run:
                print("   Please check the errors above and ensure encryption key is correct.")
        
        if dry_run:
            print("\n[DRY RUN] No changes were made. Run without --dry-run to apply changes.")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Fatal error: {str(e)}")
        raise
    finally:
        db.close()


def verify_migration():
    """
    Verify that all migrated credentials can be decrypted correctly.
    """
    db = SessionLocal()
    
    try:
        credentials = db.query(Credential).all()
        
        if not credentials:
            print("No credentials found in database.")
            return True
        
        print(f"Verifying {len(credentials)} credential(s)...")
        
        success_count = 0
        error_count = 0
        
        for cred in credentials:
            try:
                # Try to decrypt using the new format
                if cred.encrypted_data:
                    data = decrypt_credential_data(cred.encrypted_data)
                    api_key = data.get("api_key")
                    
                    # Also verify legacy format matches
                    if cred.encrypted_api_key:
                        legacy_key = decrypt_api_key(cred.encrypted_api_key)
                        if api_key != legacy_key:
                            print(f"  ⚠ Credential ID {cred.id}: Mismatch between new and legacy format!")
                            error_count += 1
                            continue
                    
                    print(f"  ✓ Credential ID {cred.id} ({cred.service_name}): OK")
                    success_count += 1
                    
                elif cred.encrypted_api_key:
                    # Legacy only - needs migration
                    print(f"  ⚠ Credential ID {cred.id} ({cred.service_name}): Not migrated (legacy only)")
                    error_count += 1
                    
                else:
                    print(f"  ✗ Credential ID {cred.id} ({cred.service_name}): No encrypted data!")
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"  ✗ Credential ID {cred.id} ({cred.service_name}): {str(e)}")
        
        print(f"\nVerification complete:")
        print(f"  - Success: {success_count}")
        print(f"  - Errors/Warnings: {error_count}")
        
        return error_count == 0
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate credentials to flexible JSON format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-migrate credentials even if encrypted_data already exists"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only verify existing migration, don't migrate"
    )
    
    args = parser.parse_args()
    
    # Check that encryption key is set
    if not os.getenv("CREDENTIALS_ENCRYPTION_KEY"):
        print("✗ ERROR: CREDENTIALS_ENCRYPTION_KEY environment variable is not set.")
        print("   Set it before running this script.")
        sys.exit(1)
    
    print("=" * 60)
    print("Credentials Migration to Flexible Format")
    print("=" * 60)
    
    if args.verify:
        print("\nRunning verification only...")
        success = verify_migration()
        sys.exit(0 if success else 1)
    
    migrate_credentials_to_flexible_format(dry_run=args.dry_run, force=args.force)
    
    if not args.dry_run:
        print("\n" + "-" * 60)
        print("Running verification...")
        verify_migration()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run --verify to confirm all credentials are accessible")
    print("2. Test the application to ensure credentials work correctly")
    print("3. The encrypted_api_key column is kept for backward compatibility")
    print("4. In a future release, you can drop encrypted_api_key after all")
    print("   code is updated to use encrypted_data exclusively")
