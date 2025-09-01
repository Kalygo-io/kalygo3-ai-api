import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile
from src.services.reranking_upload_service import RerankingUploadService

@pytest.fixture
def mock_upload_file():
    """Create a mock upload file for testing"""
    file = Mock(spec=UploadFile)
    file.filename = "test_document.txt"
    file.content_type = "text/plain"
    file.read = AsyncMock(return_value=b"Test content for reranking")
    return file

@pytest.fixture
def reranking_upload_service():
    """Create a reranking upload service instance"""
    return RerankingUploadService()

def test_reranking_upload_service_initialization():
    """Test that the reranking upload service initializes with correct defaults"""
    service = RerankingUploadService()
    
    assert service.pubsub_topic_name == "txt-ingest-topic"
    assert service.namespace == "reranking"
    assert service.gcs_bucket_name == "kalygo-kb-ingest-storage"
    assert service.project_id == "kalygo-436411"

@pytest.mark.asyncio
async def test_reranking_upload_service_upload_file_and_publish(mock_upload_file, reranking_upload_service):
    """Test that the reranking upload service can upload files and publish messages"""
    # Mock the GCS and PubSub clients
    with patch('src.services.reranking_upload_service.GCSClient') as mock_gcs_client, \
         patch('src.services.reranking_upload_service.PubSubClient') as mock_pubsub_client:
        
        # Mock GCS client
        mock_storage_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_gcs_client.get_storage_client.return_value = mock_storage_client
        mock_storage_client.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        # Mock PubSub client
        mock_publisher_client = Mock()
        mock_topic_path = "projects/test-project/topics/txt-ingest-topic"
        mock_pubsub_client.get_publisher_client.return_value = mock_publisher_client
        mock_publisher_client.topic_path.return_value = mock_topic_path
        
        # Mock the publish future
        mock_future = Mock()
        mock_future.result.return_value = "test-message-id"
        mock_publisher_client.publish.return_value = mock_future
        
        result = await reranking_upload_service.upload_file_and_publish(
            file=mock_upload_file,
            user_id="test-user-id",
            user_email="test@example.com",
            jwt="test-jwt"
        )
        
        # Verify GCS operations
        mock_gcs_client.get_storage_client.assert_called_once()
        mock_storage_client.get_bucket.assert_called_once_with("kalygo-kb-ingest-storage")
        mock_bucket.blob.assert_called_once()
        mock_blob.upload_from_string.assert_called_once_with(b"Test content for reranking", content_type="text/plain")
        
        # Verify PubSub operations
        mock_pubsub_client.get_publisher_client.assert_called_once()
        mock_publisher_client.topic_path.assert_called_once_with("kalygo-436411", "txt-ingest-topic")
        mock_publisher_client.publish.assert_called_once()
        
        # Verify the result
        assert result["success"] is True
        assert result["filename"] == "test_document.txt"
        assert result["processing_status"] == "pending"
        assert result["module"] == "reranking"
        assert result["pubsub_topic"] == "txt-ingest-topic"

@pytest.mark.asyncio
async def test_reranking_upload_service_with_custom_namespace(mock_upload_file, reranking_upload_service):
    """Test that the reranking upload service can use a custom namespace"""
    with patch('src.services.reranking_upload_service.GCSClient') as mock_gcs_client, \
         patch('src.services.reranking_upload_service.PubSubClient') as mock_pubsub_client:
        
        # Mock the clients
        mock_gcs_client.get_storage_client.return_value = Mock()
        mock_pubsub_client.get_publisher_client.return_value = Mock()
        
        # Mock the publish future
        mock_future = Mock()
        mock_future.result.return_value = "test-message-id"
        mock_pubsub_client.get_publisher_client.return_value.publish.return_value = mock_future
        
        result = await reranking_upload_service.upload_file_and_publish(
            file=mock_upload_file,
            user_id="test-user-id",
            user_email="test@example.com",
            namespace="custom-namespace",
            jwt="test-jwt"
        )
        
        # Verify the result contains the custom namespace
        assert result["success"] is True
        assert result["namespace"] == "custom-namespace"

@pytest.mark.asyncio
async def test_reranking_upload_service_error_handling(mock_upload_file, reranking_upload_service):
    """Test that the reranking upload service handles errors gracefully"""
    # Mock GCS client to raise an exception
    with patch('src.services.reranking_upload_service.GCSClient') as mock_gcs_client:
        mock_gcs_client.get_storage_client.side_effect = Exception("GCS connection failed")
        
        result = await reranking_upload_service.upload_file_and_publish(
            file=mock_upload_file,
            user_id="test-user-id",
            user_email="test@example.com",
            jwt="test-jwt"
        )
        
        # Verify error handling
        assert result["success"] is False
        assert "error" in result
        assert "GCS connection failed" in result["error"]
        assert result["module"] == "reranking"
