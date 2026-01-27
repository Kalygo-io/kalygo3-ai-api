# Credentials Management Scripts

This document explains the scripts available for managing credentials encryption.

## Available Scripts

1. **rotate_credentials_encryption_key.py** - Rotate encryption keys
2. **migrate_credentials_to_flexible_format.py** - Migrate to new flexible JSON format

---

# Script 1: Encryption Key Rotation

If you change `CREDENTIALS_ENCRYPTION_KEY` without proper rotation, all existing encrypted API keys will become unreadable. The system now supports key rotation to avoid this issue.

## How Key Rotation Works

The encryption system supports multiple keys:
- **CREDENTIALS_ENCRYPTION_KEY**: Current/primary key (used for encryption)
- **CREDENTIALS_ENCRYPTION_KEY_OLD**: Previous key(s) (used for decryption, comma-separated)

When decrypting, the system tries all keys in order until one succeeds. This allows seamless rotation without losing access to existing credentials.

## Steps to Rotate Keys

### 1. Generate a New Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save this key securely.

### 2. Set Environment Variables

Set both the old and new keys:

```bash
export CREDENTIALS_ENCRYPTION_KEY_OLD="<current_key>"
export CREDENTIALS_ENCRYPTION_KEY="<new_key>"
```

### 3. Test the Rotation (Dry Run)

```bash
python scripts/rotate_credentials_encryption_key.py --dry-run
```

This will show what would be re-encrypted without making changes.

### 4. Perform the Rotation

```bash
python scripts/rotate_credentials_encryption_key.py
```

This will:
- Decrypt all credentials using the old key
- Re-encrypt them with the new key
- Update the database

### 5. Verify and Clean Up

1. Verify that credentials can be accessed correctly through the API
2. Remove `CREDENTIALS_ENCRYPTION_KEY_OLD` from your environment
3. Update `CREDENTIALS_ENCRYPTION_KEY` in all deployment environments

## Production Deployment

For production deployments (e.g., Google Cloud Run):

1. **Update secrets**:
   ```bash
   # Add old key as a new secret
   echo -n "<old_key>" | gcloud secrets create CREDENTIALS_ENCRYPTION_KEY_OLD --data-file=-
   
   # Update the current key
   echo -n "<new_key>" | gcloud secrets versions create CREDENTIALS_ENCRYPTION_KEY --data-file=-
   ```

2. **Run the rotation script** in a maintenance window or as a one-time job

3. **Remove the old key** after verification:
   ```bash
   gcloud secrets delete CREDENTIALS_ENCRYPTION_KEY_OLD
   ```

## Important Notes

- **Backup first**: Always backup your database before rotating keys
- **Test in staging**: Test the rotation process in a staging environment first
- **Maintenance window**: Consider running rotation during a maintenance window
- **Monitor**: Watch for errors during and after rotation
- **Keep old key temporarily**: Keep `CREDENTIALS_ENCRYPTION_KEY_OLD` set until you're confident the rotation succeeded

## Troubleshooting

### "Failed to decrypt API key" errors

- Ensure `CREDENTIALS_ENCRYPTION_KEY_OLD` is set to the key that was used to encrypt the credentials
- Check that the key format is correct (base64-encoded Fernet key)
- Verify the key hasn't been corrupted

### Some credentials fail to re-encrypt

- Check the error messages for specific credential IDs
- Those credentials may have been encrypted with a different key
- You may need to add additional old keys (comma-separated)

### Key rotation script fails

- Ensure database connection is working
- Check that you have write permissions
- Verify environment variables are set correctly
- Review the error output for specific issues

---

# Script 2: Migrate to Flexible Format

The credentials table now supports flexible credential types (API keys, database connections, OAuth, etc.). This script migrates existing credentials from the legacy format to the new JSON format.

## Background

**Legacy format**: `encrypted_api_key` column stores encrypted string
**New format**: `encrypted_data` column stores encrypted JSON: `{"api_key": "..."}`

The new format supports any credential structure:
- API keys: `{"api_key": "sk-..."}`
- Database connections: `{"host": "...", "port": 5432, "username": "...", "password": "..."}`
- OAuth: `{"client_id": "...", "client_secret": "...", "access_token": "..."}`

## Prerequisites

1. Run the Alembic migration first:
   ```bash
   alembic upgrade head
   ```
   This adds the `credential_type`, `encrypted_data`, and `metadata` columns.

2. Ensure `CREDENTIALS_ENCRYPTION_KEY` is set.

## Migration Steps

### 1. Test the Migration (Dry Run)

```bash
python scripts/migrate_credentials_to_flexible_format.py --dry-run
```

This shows what would be migrated without making changes.

### 2. Perform the Migration

```bash
python scripts/migrate_credentials_to_flexible_format.py
```

This will:
- Read each credential's `encrypted_api_key`
- Decrypt it
- Re-encrypt as JSON `{"api_key": "..."}`
- Store in `encrypted_data`
- Set `credential_type` to "api_key"
- Keep `encrypted_api_key` for backward compatibility

### 3. Verify the Migration

```bash
python scripts/migrate_credentials_to_flexible_format.py --verify
```

This confirms all credentials can be decrypted correctly.

### 4. Force Re-Migration (Optional)

If you need to re-migrate credentials that already have `encrypted_data`:

```bash
python scripts/migrate_credentials_to_flexible_format.py --force
```

## Backward Compatibility

The migration preserves backward compatibility:

1. **Both columns populated**: After migration, both `encrypted_api_key` and `encrypted_data` contain valid data
2. **Code uses fallback**: The `get_credential_value()` function tries `encrypted_data` first, falls back to `encrypted_api_key`
3. **Legacy endpoints work**: Old API endpoints continue to function

## Future: Removing Legacy Column

After verifying all code uses the new format:

1. Update all code to use `encrypted_data` exclusively
2. Create a migration to drop `encrypted_api_key`:
   ```python
   def upgrade():
       op.drop_column('credentials', 'encrypted_api_key')
   ```
3. Remove backward compatibility code from `encryption.py`

## Troubleshooting

### "No credentials found in database"

The database is empty or the query failed. Check database connection.

### "Already migrated" message

Credentials already have `encrypted_data`. Use `--force` to re-migrate.

### Verification shows mismatches

The `encrypted_data` and `encrypted_api_key` contain different values. Re-run migration with `--force`.

### Decryption errors

- Check `CREDENTIALS_ENCRYPTION_KEY` is correct
- If keys were rotated, ensure `CREDENTIALS_ENCRYPTION_KEY_OLD` is set
- Run key rotation script first if needed

