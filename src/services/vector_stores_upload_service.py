import logging
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import UploadFile
from src.clients.gcs_client import GCSClient
from src.clients.pubsub_client import PubSubClient

logger = logging.getLogger(__name__)

class VectorStoresUploadService:
    """
    Upload service for the Vector Stores module.
    Uploads files to Google Cloud Storage and publishes messages to PubSub topic 'vector-stores-ingest-topic'.
    Supports multiple indexes and namespaces.
    """
    
    def __init__(self):
        self.gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "kalygo-kb-ingest-storage")
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
        batch_number: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file to GCS and publish a message to Pub/Sub for async processing.
        """
        try:
            file_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            if batch_number is None:
                batch_number = str(uuid.uuid4())
            
            gcs_file_path = f"vector_stores/{index_name}/{namespace}/{batch_number}/{file_id}/{file.filename}"
            
            storage_client = GCSClient.get_storage_client()
            bucket = storage_client.get_bucket(self.gcs_bucket_name)
            blob = bucket.blob(gcs_file_path)
            
            file_content = await file.read()
            blob.upload_from_string(file_content, content_type=file.content_type)

            logger.info("File uploaded to GCS: %s", gcs_file_path)
            
            message_data = {
                "file_id": file_id,
                "filename": file.filename,
                "gcs_bucket": self.gcs_bucket_name,
                "gcs_file_path": gcs_file_path,
                "file_size": len(file_content),
                "content_type": file.content_type,
                "user_id": user_id,
                "user_email": user_email,
                "index_name": index_name,
                "namespace": namespace,
                "batch_number": batch_number,
                "upload_timestamp": timestamp,
                "processing_status": "pending",
                "jwt": jwt,
                "module": "vector_stores",
                "comment": comment
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
            
        except Exception:
            logger.exception("Error in VectorStoresUploadService")
            return {
                "success": False,
                "error": "Failed to upload file. Please try again.",
                "module": "vector_stores"
            }
