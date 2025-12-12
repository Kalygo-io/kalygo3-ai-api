# Credentials Encryption Key Rotation

This document explains how to rotate the encryption key used for storing API keys.

## Current Limitation

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

