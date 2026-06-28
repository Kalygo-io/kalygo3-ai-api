import logging
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session
from src.services import account_gcs_service
from src.clients.pubsub_client import PubSubClient

logger = logging.getLogger(__name__)

class VectorStoresUploadService:
    """
    Upload service for the Vector Stores module.

    Uploads files to the account's OWN Google Cloud Storage bucket (per-account
    credentials) and publishes a message to the 'qna-ingest-topic' Pub/Sub topic
    for async ingestion. The Pub/Sub message carries account_id so the ingest
    cloud function can resolve the same per-account credentials to download.
    """

    def __init__(self):
        self.pubsub_topic_name = "qna-ingest-topic"
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "kalygo-436411")

    async def upload_file_and_publish(
        self,
        file: UploadFile,
        user_id: str,
        user_email: str,
        index_name: str,
        namespace: str,
        jwt: str,
        db: Session,
        account_id: int,
        batch_number: Optional[str] = None,
        comment: Optional[str] = None,
        extra_message_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload file to the account's GCS bucket and publish a message to Pub/Sub.

        `extra_message_fields` are merged into the published Pub/Sub message. The
        PDF-to-FAQ flow uses this to carry the reviewed Q&A pairs (so the ingest
        cloud function builds vectors from them) alongside the original PDF that
        is the stored/referenced source.

        Raises account_gcs_service.AccountGcsCredentialMissing when the account
        has no GCS credential configured (callers map this to HTTP 400).
        """
        try:
            file_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()

            if batch_number is None:
                batch_number = str(uuid.uuid4())

            gcs_file_path = f"vector_stores/{index_name}/{namespace}/{batch_number}/{file_id}/{file.filename}"

            file_content = await file.read()

            # Store in the bucket bound to this knowledge base (falls back to the
            # owner's default GCS credential when the index has no explicit bind).
            ref = account_gcs_service.upload_bytes_for_index(
                db,
                account_id,
                index_name,
                file_bytes=file_content,
                gcs_file_path=gcs_file_path,
                content_type=file.content_type,
            )
            gcs_bucket = ref["gcs_bucket"]

            logger.info("File uploaded to GCS: gs://%s/%s", gcs_bucket, gcs_file_path)

            message_data = {
                "file_id": file_id,
                "filename": file.filename,
                "gcs_bucket": gcs_bucket,
                "gcs_file_path": gcs_file_path,
                "file_size": len(file_content),
                "content_type": file.content_type,
                "user_id": user_id,
                "user_email": user_email,
                "account_id": account_id,
                "index_name": index_name,
                "namespace": namespace,
                "batch_number": batch_number,
                "upload_timestamp": timestamp,
                "processing_status": "pending",
                "jwt": jwt,
                "module": "vector_stores",
                "comment": comment
            }

            if extra_message_fields:
                message_data.update(extra_message_fields)

            publisher_client = PubSubClient.get_publisher_client()
            topic_path = publisher_client.topic_path(self.project_id, self.pubsub_topic_name)
            
            message_json = json.dumps(message_data)
            message_bytes = message_json.encode("utf-8")
            
            future = publisher_client.publish(topic_path, data=message_bytes)
            message_id = future.result()
            
            logger.info("Published message %s for file %s", message_id, file.filename)
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": file.filename,
                "gcs_bucket": gcs_bucket,
                "gcs_file_path": gcs_file_path,
                "message_id": message_id,
                "batch_number": batch_number,
                "index_name": index_name,
                "namespace": namespace,
                "processing_status": "pending",
                "message": "File uploaded successfully and queued for vector database ingestion",
                "pubsub_topic": self.pubsub_topic_name,
                "module": "vector_stores"
            }

        except account_gcs_service.AccountGcsCredentialMissing:
            # Propagate so the router can return a clear HTTP 400 prompting the
            # account to configure GCS credentials.
            raise
        except Exception:
            logger.exception("Error in VectorStoresUploadService")
            return {
                "success": False,
                "error": "Failed to upload file. Please try again.",
                "module": "vector_stores"
            }
