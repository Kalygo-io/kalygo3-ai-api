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
from datetime import timedelta
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from google.cloud import storage
from google.oauth2 import service_account

from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_credential_data
from src.services.credential_access import resolve_default_credential

logger = logging.getLogger(__name__)


class AccountGcsCredentialMissing(Exception):
    """Raised when an account has no usable GOOGLE_CLOUD_STORAGE credential."""
    pass


def _resolve_account_gcs_service_account(db: Session, account_id: int) -> Dict[str, Any]:
    """
    Return just the decrypted service-account JSON for the account's GCS
    credential (no bucket required), or raise AccountGcsCredentialMissing.

    Used by signing paths that already know the exact bucket (e.g. the bucket
    recorded in the ingestion log) and only need the private key to sign.
    """
    credential = resolve_default_credential(db, account_id, ServiceName.GOOGLE_CLOUD_STORAGE)

    if not credential:
        raise AccountGcsCredentialMissing(
            "This account has no Google Cloud Storage credentials configured. "
            "Add them in Credentials before uploading files."
        )

    try:
        data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        logger.error("[ACCOUNT GCS] Failed to decrypt GCS credential for account %s: %s", account_id, e)
        raise AccountGcsCredentialMissing(
            "The stored Google Cloud Storage credential could not be read. "
            "Please re-enter it in Credentials."
        )

    service_account_json = data.get("service_account_json")
    if not service_account_json:
        raise AccountGcsCredentialMissing(
            "The Google Cloud Storage credential is incomplete. It must include a "
            "service-account JSON."
        )
    return service_account_json


def _resolve_account_gcs_config(db: Session, account_id: int) -> Tuple[Dict[str, Any], str]:
    """
    Return (service_account_json, bucket_name) for the account, or raise
    AccountGcsCredentialMissing if no valid credential is configured.
    """
    # Resolve the account's default GCS credential, considering both owned and
    # shared credentials (falls back to most-recent owned/shared if no explicit
    # default is set).
    credential = resolve_default_credential(db, account_id, ServiceName.GOOGLE_CLOUD_STORAGE)

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


def _config_from_credential(credential) -> Tuple[Dict[str, Any], str]:
    """Extract (service_account_json, bucket_name) from a specific GCS credential."""
    metadata = credential.credential_metadata or {}
    bucket_name = metadata.get("bucket_name")
    try:
        data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        logger.error("[ACCOUNT GCS] Failed to decrypt GCS credential %s: %s", credential.id, e)
        raise AccountGcsCredentialMissing(
            "The stored Google Cloud Storage credential could not be read. "
            "Please re-enter it in Credentials."
        )
    service_account_json = data.get("service_account_json")
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


def upload_bytes_for_index(
    db: Session,
    owner_account_id: int,
    index_name: str,
    *,
    file_bytes: bytes,
    gcs_file_path: str,
    content_type: Optional[str] = None,
) -> Dict[str, str]:
    """
    Upload bytes for a specific knowledge base, using that index's bound GCS
    credential/bucket (falling back to the owner's default when unbound).

    Keeps a KB's source files in the bucket its VectorStore binds, so retrieval
    (which signs against the bucket recorded at ingest) stays consistent even if
    the owner's account-level default GCS credential later changes.
    """
    # Imported lazily to avoid a heavier import graph at module load.
    from src.services.vector_store_credentials import resolve_index_gcs_credential

    credential = resolve_index_gcs_credential(db, owner_account_id, index_name)
    if not credential:
        raise AccountGcsCredentialMissing(
            "This knowledge base has no Google Cloud Storage credential configured. "
            "Add one in Credentials (or bind one to the knowledge base) before uploading files."
        )
    service_account_json, bucket_name = _config_from_credential(credential)

    client = _build_storage_client(service_account_json)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_file_path)
    blob.upload_from_string(file_bytes, content_type=content_type)

    logger.info(
        "[ACCOUNT GCS] Uploaded gs://%s/%s for index %s (owner %s)",
        bucket_name, gcs_file_path, index_name, owner_account_id,
    )
    return {"gcs_bucket": bucket_name, "gcs_file_path": gcs_file_path}


def generate_signed_url(
    db: Session,
    account_id: int,
    *,
    gcs_file_path: str,
    expiration_seconds: int = 900,
) -> str:
    """
    Generate a short-lived V4 signed GET URL for an object in the account's
    bucket. Signing is done locally with the account's service-account private
    key (no extra IAM permission needed beyond holding the key).

    The bucket is always resolved from the account's own credential — the caller
    cannot point this at an arbitrary bucket. Raises AccountGcsCredentialMissing
    if the account has no GCS credential.
    """
    service_account_json, bucket_name = _resolve_account_gcs_config(db, account_id)

    client = _build_storage_client(service_account_json)
    blob = client.bucket(bucket_name).blob(gcs_file_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expiration_seconds),
        method="GET",
    )


def generate_signed_url_for(
    db: Session,
    owner_account_id: int,
    *,
    gcs_bucket: str,
    gcs_file_path: str,
    expiration_seconds: int = 900,
) -> str:
    """
    Generate a short-lived V4 signed GET URL for an object in an EXPLICIT bucket,
    signed with *owner_account_id*'s service-account key.

    Unlike generate_signed_url, the bucket is supplied by the caller (e.g. the
    bucket recorded in the ingestion log at ingest time) rather than re-resolved
    from the owner's current default credential. This keeps previously-ingested
    source files reachable even if the owner later changes their default GCS
    credential. The caller MUST have already authorized access and validated that
    (owner, bucket, path) is a legitimate, access-checked object.

    Raises AccountGcsCredentialMissing if the owner has no usable GCS credential.
    """
    service_account_json = _resolve_account_gcs_service_account(db, owner_account_id)
    client = _build_storage_client(service_account_json)
    blob = client.bucket(gcs_bucket).blob(gcs_file_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expiration_seconds),
        method="GET",
    )
