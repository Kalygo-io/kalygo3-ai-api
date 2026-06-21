import logging
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import UploadFile
from sqlalchemy.orm import Session
from src.services import account_gcs_service
from src.clients.pubsub_client import PubSubClient

logger = logging.getLogger(__name__)

class FileUploadService:
    def __init__(self):
        self.pubsub_topic_name = "qna-ingest-topic"
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "kalygo-436411")

    async def upload_file_and_publish(self, file: UploadFile, user_id: str, user_email: str, namespace: str, jwt: str, db: Session, account_id: int) -> Dict[str, Any]:
        """
        Upload file to the account's GCS bucket and publish a message to Pub/Sub.

        Raises account_gcs_service.AccountGcsCredentialMissing when the account
        has no GCS credential configured (callers map this to HTTP 400).
        """
        try:
            file_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()

            gcs_file_path = f"similarity_search/{namespace}/{file_id}/{file.filename}"

            file_content = await file.read()

            ref = account_gcs_service.upload_bytes(
                db,
                account_id,
                file_bytes=file_content,
                gcs_file_path=gcs_file_path,
                content_type=file.content_type,
            )
            gcs_bucket = ref["gcs_bucket"]

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
                "namespace": namespace,
                "upload_timestamp": timestamp,
                "processing_status": "pending",
                "jwt": jwt
            }

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
                "processing_status": "pending",
                "message": "File uploaded successfully and queued for processing"
            }

        except account_gcs_service.AccountGcsCredentialMissing:
            raise
        except Exception as e:
            logger.exception("Error uploading file and publishing message")
            return {
                "success": False,
                "error": "Failed to upload file. Please try again."
            }
