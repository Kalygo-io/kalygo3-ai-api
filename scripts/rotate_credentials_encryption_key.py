"""
Script to rotate encryption keys for stored credentials.

This script re-encrypts all credentials in the database with a new encryption key.
It should be run when rotating the CREDENTIALS_ENCRYPTION_KEY.

Usage:
    1. Set CREDENTIALS_ENCRYPTION_KEY_OLD to the current key
    2. Set CREDENTIALS_ENCRYPTION_KEY to the new key
    3. Run: python scripts/rotate_credentials_encryption_key.py
    4. After successful rotation, remove CREDENTIALS_ENCRYPTION_KEY_OLD

Example:
    export CREDENTIALS_ENCRYPTION_KEY_OLD="old_key_here"
    export CREDENTIALS_ENCRYPTION_KEY="new_key_here"
    python scripts/rotate_credentials_encryption_key.py
"""
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db.database import SessionLocal
from src.db.models import Credential
from src.routers.credentials.encryption import encrypt_api_key, decrypt_api_key

load_dotenv()

def rotate_credentials_encryption_key(dry_run: bool = False):
    """
    Re-encrypt all credentials with the new encryption key.
    
    Args:
        dry_run: If True, only shows what would be re-encrypted without making changes
    """
    db = SessionLocal()
    
    try:
        # Get all credentials
        credentials = db.query(Credential).all()
        
        if not credentials:
            print("No credentials found in database.")
            return
        
        print(f"Found {len(credentials)} credential(s) to process.")
        
        if dry_run:
            print("\n[DRY RUN] Would re-encrypt the following credentials:")
        else:
            print("\nRe-encrypting credentials...")
        
        success_count = 0
        error_count = 0
        
        for cred in credentials:
            try:
                # Decrypt with old key (or current key if no old key set)
                decrypted_key = decrypt_api_key(cred.encrypted_api_key)
                
                if dry_run:
                    print(f"  - Credential ID {cred.id} ({cred.service_name}): OK")
                else:
                    # Re-encrypt with new key
                    new_encrypted_key = encrypt_api_key(decrypted_key)
                    cred.encrypted_api_key = new_encrypted_key
                    db.add(cred)
                    success_count += 1
                    print(f"  ✓ Re-encrypted credential ID {cred.id} ({cred.service_name})")
                    
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error processing credential ID {cred.id} ({cred.service_name}): {str(e)}")
        
        if not dry_run:
            if success_count > 0:
                db.commit()
                print(f"\n✓ Successfully re-encrypted {success_count} credential(s).")
            else:
                db.rollback()
                print("\n✗ No credentials were re-encrypted. Rolling back changes.")
        
        if error_count > 0:
            print(f"\n⚠ {error_count} credential(s) could not be processed.")
            if not dry_run:
                print("   Please check the errors above and ensure CREDENTIALS_ENCRYPTION_KEY_OLD is set correctly.")
        
        if dry_run:
            print("\n[DRY RUN] No changes were made. Run without --dry-run to apply changes.")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Fatal error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rotate encryption keys for stored credentials"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be re-encrypted without making changes"
    )
    
    args = parser.parse_args()
    
    # Check that encryption keys are set
    if not os.getenv("CREDENTIALS_ENCRYPTION_KEY"):
        print("✗ ERROR: CREDENTIALS_ENCRYPTION_KEY environment variable is not set.")
        print("   Set it to the new encryption key before running this script.")
        sys.exit(1)
    
    if not os.getenv("CREDENTIALS_ENCRYPTION_KEY_OLD"):
        print("⚠ WARNING: CREDENTIALS_ENCRYPTION_KEY_OLD is not set.")
        print("   This script will try to decrypt with the current key.")
        response = input("   Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("   Aborted.")
            sys.exit(1)
    
    print("=" * 60)
    print("Credentials Encryption Key Rotation Script")
    print("=" * 60)
    
    rotate_credentials_encryption_key(dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    print("Rotation complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify that credentials can be accessed correctly")
    print("2. Remove CREDENTIALS_ENCRYPTION_KEY_OLD after verification")
    print("3. Update CREDENTIALS_ENCRYPTION_KEY in all environments")

