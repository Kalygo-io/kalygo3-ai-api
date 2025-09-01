import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import UploadFile
from src.clients.gcs_client import GCSClient
from src.clients.pubsub_client import PubSubClient

class RerankingUploadService:
    """
    Independent upload service for the reranking module.
    Uploads files to Google Cloud Storage and publishes messages to PubSub topic 'txt-ingest-topic'.
    """
    
    def __init__(self):
        self.gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "kalygo-kb-ingest-storage")
        self.pubsub_topic_name = "txt-ingest-topic"  # Fixed topic for reranking
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "kalygo-436411")
        self.namespace = "reranking"
    
    async def upload_file_and_publish(self, file: UploadFile, user_id: str, user_email: str, namespace: str = None, jwt: str = None) -> Dict[str, Any]:
        """
        Upload file to GCS and publish a message to Pub/Sub for async processing.
        
        Args:
            file: The uploaded file
            user_id: The user ID from JWT
            user_email: The user email from JWT
            namespace: The namespace (defaults to "reranking")
            jwt: JWT token for authentication
            
        Returns:
            Dict containing upload status and file information
        """
        try:
            print("*** RerankingUploadService.upload_file_and_publish ***")

            # Use provided namespace or default to reranking
            if namespace is None:
                namespace = self.namespace

            # Generate unique file ID
            file_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create GCS file path
            gcs_file_path = f"reranking/{namespace}/{file_id}/{file.filename}"
            
            # Upload file to GCS
            storage_client = GCSClient.get_storage_client()
            bucket = storage_client.get_bucket(self.gcs_bucket_name)
            blob = bucket.blob(gcs_file_path)
            
            # Read file content and upload
            file_content = await file.read()
            blob.upload_from_string(file_content, content_type=file.content_type)

            print(f"File uploaded to GCS: {gcs_file_path}")
            print(f"User email: {user_email}")
            
            # Prepare message data for Pub/Sub
            message_data = {
                "file_id": file_id,
                "filename": file.filename,
                "gcs_bucket": self.gcs_bucket_name,
                "gcs_file_path": gcs_file_path,
                "file_size": len(file_content),
                "content_type": file.content_type,
                "user_id": user_id,
                "user_email": user_email,
                "namespace": namespace,
                "upload_timestamp": timestamp,
                "processing_status": "pending",
                "jwt": jwt,
                "module": "reranking"  # Identify this as a reranking upload
            }

            # Publish message to Pub/Sub
            publisher_client = PubSubClient.get_publisher_client()
            topic_path = publisher_client.topic_path(self.project_id, self.pubsub_topic_name)
            
            # Convert message data to JSON string
            message_json = json.dumps(message_data)
            message_bytes = message_json.encode("utf-8")
            
            # Publish the message
            future = publisher_client.publish(topic_path, data=message_bytes)
            message_id = future.result()
            
            print(f"Published message {message_id} to topic {self.pubsub_topic_name} for file {file.filename}")
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": file.filename,
                "gcs_file_path": gcs_file_path,
                "message_id": message_id,
                "processing_status": "pending",
                "message": "File uploaded successfully and queued for reranking processing",
                "pubsub_topic": self.pubsub_topic_name,
                "module": "reranking"
            }
            
        except Exception as e:
            print(f"Error in RerankingUploadService: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to upload file and publish message: {str(e)}",
                "module": "reranking"
            }
