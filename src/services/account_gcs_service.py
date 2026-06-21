"""
Per-account Google Cloud Storage service.

Resolves an account's GOOGLE_CLOUD_STORAGE credential (stored via the flexible
Credentials system), decrypts the service-account JSON, builds a storage client
scoped to that account, and uploads bytes to the account's own bucket.

This is the single place per-account GCS credentials are resolved and the single
gate that blocks uploads when an account has not configured GCS credentials —
callers translate AccountGcsCredentialMissing into an HTTP 400.

The bucket name is stored as non-secret metadata on the credential
(credential_metadata["bucket_name"]); the service-account JSON is stored inside
the encrypted credential data under "service_account_json".
"""
import logging
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from google.cloud import storage
from google.oauth2 import service_account

from src.db.models import Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_credential_data

logger = logging.getLogger(__name__)


class AccountGcsCredentialMissing(Exception):
    """Raised when an account has no usable GOOGLE_CLOUD_STORAGE credential."""
    pass


def _resolve_account_gcs_config(db: Session, account_id: int) -> Tuple[Dict[str, Any], str]:
    """
    Return (service_account_json, bucket_name) for the account, or raise
    AccountGcsCredentialMissing if no valid credential is configured.
    """
    credential = (
        db.query(Credential)
        .filter(
            Credential.account_id == account_id,
            Credential.credential_type == ServiceName.GOOGLE_CLOUD_STORAGE,
        )
        .order_by(Credential.updated_at.desc())
        .first()
    )

    if not credential:
        raise AccountGcsCredentialMissing(
            "This account has no Google Cloud Storage credentials configured. "
            "Add them in Credentials before uploading files."
        )

    # Bucket name is non-secret metadata.
    metadata = credential.credential_metadata or {}
    bucket_name = metadata.get("bucket_name")

    try:
        data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        logger.error("[ACCOUNT GCS] Failed to decrypt GCS credential for account %s: %s", account_id, e)
        raise AccountGcsCredentialMissing(
            "The stored Google Cloud Storage credential could not be read. "
            "Please re-enter it in Credentials."
        )

    service_account_json = data.get("service_account_json")
    # Allow the bucket to live inside the encrypted blob too, as a fallback.
    bucket_name = bucket_name or data.get("bucket_name")

    if not service_account_json or not bucket_name:
        raise AccountGcsCredentialMissing(
            "The Google Cloud Storage credential is incomplete. It must include a "
            "service-account JSON and a bucket name."
        )

    return service_account_json, bucket_name


def _build_storage_client(service_account_json: Dict[str, Any]) -> storage.Client:
    """Build a GCS client from a per-account service-account JSON object."""
    credentials = service_account.Credentials.from_service_account_info(service_account_json)
    project = service_account_json.get("project_id")
    return storage.Client(credentials=credentials, project=project)


def get_account_bucket_name(db: Session, account_id: int) -> str:
    """Return the configured bucket name for an account (raises if missing)."""
    _, bucket_name = _resolve_account_gcs_config(db, account_id)
    return bucket_name


def upload_bytes(
    db: Session,
    account_id: int,
    *,
    file_bytes: bytes,
    gcs_file_path: str,
    content_type: Optional[str] = None,
) -> Dict[str, str]:
    """
    Upload bytes to the account's GCS bucket at gcs_file_path.

    Returns {"gcs_bucket": ..., "gcs_file_path": ...}.
    Raises AccountGcsCredentialMissing if the account has no GCS credential.
    """
    service_account_json, bucket_name = _resolve_account_gcs_config(db, account_id)

    client = _build_storage_client(service_account_json)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_file_path)
    blob.upload_from_string(file_bytes, content_type=content_type)

    logger.info("[ACCOUNT GCS] Uploaded gs://%s/%s for account %s", bucket_name, gcs_file_path, account_id)

    return {"gcs_bucket": bucket_name, "gcs_file_path": gcs_file_path}
