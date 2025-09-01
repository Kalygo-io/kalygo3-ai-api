# Async File Processing System - Publish Side

This document explains how the file upload and publishing system works for the similarity search feature.

## Overview

When a file is uploaded to the `similaritySearch/upload` endpoint, the system:

1. **Uploads the file to Google Cloud Storage (GCS)**
2. **Publishes a message to Google Cloud Pub/Sub**
3. **Returns immediately with a success response**

The actual processing (chunking and uploading to Pinecone) happens asynchronously via a separate subscriber service.

## Architecture

```
Client Upload → FastAPI → GCS Upload → Pub/Sub Message → Async Processing
```

## Components

### 1. Upload Endpoints

- **`/api/similarity-search/upload-single`**: Upload a single file
- **`/api/similarity-search/upload`**: Upload multiple files

Both endpoints:
- Validate file type (only `.csv` files supported)
- Require JWT authentication
- Upload to GCS and publish to Pub/Sub
- Return immediately with upload status

### 2. FileUploadService

Located in `src/services/file_upload_service.py`

**Key Methods:**
- `upload_file_and_publish()`: Main method that handles both GCS upload and Pub/Sub publishing

**Process:**
1. Generate unique file ID
2. Create GCS file path: `similarity-search/{namespace}/{file_id}/{filename}`
3. Upload file content to GCS
4. Prepare message data with file metadata
5. Publish message to Pub/Sub topic
6. Return success response

### 3. Pub/Sub Message Structure

```json
{
  "file_id": "uuid-string",
  "filename": "example.csv",
  "gcs_bucket": "swarms",
  "gcs_file_path": "similarity-search/similarity_search/uuid/filename.csv",
  "file_size": 1024,
  "content_type": "text/csv",
  "user_id": "user-id-from-jwt",
  "namespace": "similarity_search",
  "upload_timestamp": "2024-01-01T12:00:00",
  "processing_status": "pending"
}
```

## Environment Variables

Required environment variables:

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_NAME=swarms
GCS_SA_PATH=/path/to/service-account.json  # For local development
GCS_SA={"type": "service_account", ...}    # For production (JSON string)

# Pub/Sub
PUBSUB_TOPIC_NAME=file-processing
```

## API Response Format

### Success Response
```json
{
  "success": true,
  "file_id": "uuid-string",
  "filename": "example.csv",
  "gcs_file_path": "similarity-search/similarity_search/uuid/filename.csv",
  "message_id": "pubsub-message-id",
  "processing_status": "pending",
  "message": "File uploaded successfully and queued for processing"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error description"
}
```

## File Requirements

- **File Type**: Only `.csv` files are supported
- **CSV Structure**: Must contain `q` and `a` columns
- **Authentication**: JWT token required
- **File Size**: Limited by GCS and Pub/Sub limits

## Error Handling

The system handles various error scenarios:

1. **Authentication errors**: Returns 401 if JWT is missing/invalid
2. **File validation errors**: Returns error for unsupported file types
3. **GCS upload errors**: Returns error if file upload fails
4. **Pub/Sub publishing errors**: Returns error if message publishing fails

## Monitoring

The system logs:
- File upload attempts
- GCS upload success/failure
- Pub/Sub message publishing
- Error details for debugging

## Next Steps

After a file is uploaded and a message is published:

1. A separate subscriber service (not part of this system) will:
   - Listen for messages on the Pub/Sub topic
   - Download the file from GCS
   - Process the CSV (chunk into Q&A pairs)
   - Generate embeddings
   - Upload vectors to Pinecone
   - Update processing status

2. The subscriber can be implemented as:
   - A Cloud Function (serverless)
   - A Cloud Run service
   - A standalone service
   - Any other Pub/Sub subscriber

## Testing

To test the upload functionality:

1. Ensure all environment variables are set
2. Have a valid JWT token
3. Prepare a CSV file with `q` and `a` columns
4. Make a POST request to `/api/similarity-search/upload-single`
5. Check the response for success/error
6. Verify the file appears in GCS
7. Check Pub/Sub for the published message
