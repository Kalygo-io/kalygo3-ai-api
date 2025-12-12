from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Form
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import json
import hashlib
import time
import asyncio
import re
import yaml
from typing import List, Dict, Tuple, Any, Optional
from src.core.clients import pc
from src.deps import jwt_dependency
from src.services import fetch_embedding
from src.services.reranking_upload_service import RerankingUploadService
import tiktoken

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

def parse_metadata_from_file(text_content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML metadata from the top of a file and return both metadata and content without metadata.
    
    Expected format:
    - YAML metadata section at the top of the file
    - Metadata section is delimited by --- at the beginning and end
    - Example:
      ---
      video_title: "What is Ollama?"
      video_url: "https://www.youtube.com/watch/glkQIUTCAK4"
      tags:
        - tutorial
        - ollama
      ---
      
      Content starts here...
    
    Returns:
        Tuple of (metadata_dict, content_without_metadata)
    """
    metadata = {}
    lines = text_content.split('\n')
    content_lines = []
    
    # Check if file starts with YAML front matter (---)
    if lines and lines[0].strip() == '---':
        # Find the end of YAML section
        yaml_end_index = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                yaml_end_index = i
                break
        
        if yaml_end_index > 0:
            # Extract YAML content
            yaml_content = '\n'.join(lines[1:yaml_end_index])
            
            try:
                # Parse YAML metadata
                metadata = yaml.safe_load(yaml_content) or {}
                
                # Convert all values to strings for consistency
                string_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, (list, dict)):
                        string_metadata[key] = str(value)
                    else:
                        string_metadata[key] = str(value) if value is not None else ""
                
                metadata = string_metadata
                
                # Content starts after the second ---
                content_lines = lines[yaml_end_index + 1:]
                
            except yaml.YAMLError as e:
                print(f"Warning: Failed to parse YAML metadata: {e}")
                # If YAML parsing fails, treat the whole file as content
                content_lines = lines
        else:
            # No closing --- found, treat as content
            content_lines = lines
    else:
        # No YAML front matter, treat as content
        content_lines = lines
    
    content_without_metadata = '\n'.join(content_lines)
    return metadata, content_without_metadata

def prepend_metadata_to_chunk(chunk: str, chunk_index: int, total_chunks: int, file_metadata: Dict[str, Any], filename: str) -> str:
    """
    Prepend YAML front matter metadata to a chunk with additional chunk-specific metadata.
    
    Args:
        chunk: The original chunk content
        chunk_index: The index of this chunk (0-based)
        total_chunks: Total number of chunks in the file
        file_metadata: Metadata from the original file's YAML front matter
        filename: The original filename
    
    Returns:
        Chunk with prepended metadata
    """
    # Create chunk-specific metadata
    chunk_metadata = {
        "chunk_number": f"{chunk_index + 1} of {total_chunks}",  # 1-based for readability
        "filename": filename,
        "upload_timestamp_in_unix": int(time.time())
    }
    
    # Combine file metadata with chunk metadata
    combined_metadata = {**file_metadata, **chunk_metadata}
    
    # Convert to YAML format
    yaml_content = yaml.dump(combined_metadata, default_flow_style=False, sort_keys=False)
    
    # Create the final chunk with YAML front matter
    final_chunk = f"---\n{yaml_content}---\n\n{chunk}"
    
    return final_chunk

def chunk_text_by_tokens(text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
    """
    Chunk text into pieces of approximately chunk_size tokens with overlap.
    Uses tiktoken for accurate token counting.
    """
    try:
        # Use cl100k_base encoding (used by GPT-4, Claude, etc.)
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        
        chunks = []
        i = 0
        
        while i < len(tokens):
            # Take chunk_size tokens
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move forward by chunk_size - overlap
            i += chunk_size - overlap
            
            # If we're near the end, just take the remaining tokens
            if i + chunk_size >= len(tokens):
                if i < len(tokens):
                    remaining_tokens = tokens[i:]
                    remaining_text = encoding.decode(remaining_tokens)
                    if remaining_text.strip():  # Only add if not empty
                        chunks.append(remaining_text)
                break
        
        return chunks
    except Exception as e:
        # Fallback to simple character-based chunking if tiktoken fails
        print(f"Warning: tiktoken failed, using fallback chunking: {e}")
        return [text[i:i + chunk_size * 4] for i in range(0, len(text), chunk_size * 3)]

async def generate_embedding_for_chunk(chunk: str, chunk_index: int, filename: str, jwt: str, file_metadata: Dict[str, Any] = None) -> dict:
    """
    Generate embedding for a single chunk and prepare vector data for storage.
    Returns None if processing fails.
    """
    try:
        # Skip empty chunks
        if not chunk.strip():
            return None
        
        # Get embedding for the chunk
        embedding = await fetch_embedding(jwt, chunk)
        
        # Ensure embedding values are floats (Pinecone requirement)
        if embedding is not None:
            # Flatten the embedding if it's nested and convert to floats
            def flatten_and_convert(obj):
                if isinstance(obj, list):
                    return [flatten_and_convert(item) for item in obj]
                else:
                    return float(obj)
            
            # Flatten the nested structure
            flattened_embedding = []
            def flatten_list(lst):
                for item in lst:
                    if isinstance(item, list):
                        flatten_list(item)
                    else:
                        flattened_embedding.append(item)
            
            flatten_list(embedding)
            embedding_values = [float(val) for val in flattened_embedding]
        else:
            raise Exception("Failed to get embedding from API")
        
        # Create unique ID for the vector
        chunk_id = hashlib.sha256(f"{filename}_{chunk_index}_{chunk[:50]}".encode()).hexdigest()
        
        # Prepare base metadata
        metadata = {
            "filename": filename,
            "chunk_id": chunk_index,
            "content": chunk,
            "chunk_size_tokens": len(chunk.split()), # Approximate token count
            "upload_timestamp": str(int(time.time() * 1000))
        }
        
        # Add file metadata if available
        if file_metadata:
            # Prefix file metadata keys to avoid conflicts
            for key, value in file_metadata.items():
                metadata[f"file_{key}"] = value
        
        # Add chunk-specific metadata
        metadata["chunk_number"] = chunk_index + 1
        metadata["total_chunks"] = file_metadata.get("total_chunks", "unknown") if file_metadata else "unknown"
        
        # Prepare vector data
        vector_data = {
            "id": chunk_id,
            "values": embedding_values,
            "metadata": metadata
        }
        
        return vector_data
    except Exception as e:
        print(f"Error processing chunk {chunk_index}: {e}")
        return None

async def process_single_file(file: UploadFile, jwt: str, index, namespace: str, chunk_size: int = 200, overlap: int = 50) -> dict:
    """
    Process a single file: validate, chunk, and upload to Pinecone.
    Returns a result dictionary with upload statistics.
    """
    try:
        # Validate file type
        if not (file.filename.endswith('.txt') or file.filename.endswith('.md')):
            return {
                "success": False,
                "filename": file.filename,
                "error": "Only .txt and .md files are supported"
            }
        
        # Read file content
        content = await file.read()
        text_content = content.decode('utf-8')
        
        if not text_content.strip():
            return {
                "success": False,
                "filename": file.filename,
                "error": "File is empty"
            }
        
        # Parse metadata from the file
        metadata, content_without_metadata = parse_metadata_from_file(text_content)
        
        # Log metadata if found
        if metadata:
            print(f"Found YAML front matter in {file.filename}:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
        else:
            print(f"No YAML front matter found in {file.filename}")
        
        # Chunk the text using dynamic chunking parameters
        raw_chunks = chunk_text_by_tokens(content_without_metadata, chunk_size=chunk_size, overlap=overlap)
        
        if not raw_chunks:
            return {
                "success": False,
                "filename": file.filename,
                "error": "No valid chunks created from file"
            }
        
        # Prepend metadata to each chunk
        chunks_with_metadata = []
        for i, chunk in enumerate(raw_chunks):
            chunk_with_metadata = prepend_metadata_to_chunk(
                chunk, i, len(raw_chunks), metadata, file.filename
            )
            chunks_with_metadata.append(chunk_with_metadata)
        
        # Process chunks in parallel
        print(f"Processing {len(chunks_with_metadata)} chunks for {file.filename}...")
        
        # Create tasks for parallel processing
        tasks = []
        for i, chunk in enumerate(chunks_with_metadata):
            print(f"Processing chunk {i+1} of {len(chunks_with_metadata)} for {file.filename}")
            task = generate_embedding_for_chunk(chunk, i, file.filename, jwt, metadata)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        vectors_to_upsert = []
        successful_chunks = 0
        failed_chunks = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception processing chunk {i} for {file.filename}: {result}")
                failed_chunks += 1
            elif result is not None:
                # Add total_chunks to metadata
                result["metadata"]["total_chunks"] = len(chunks_with_metadata)
                vectors_to_upsert.append(result)
                successful_chunks += 1
            else:
                failed_chunks += 1
        
        # Upload vectors to Pinecone in batches
        if vectors_to_upsert:
            # Pinecone recommends batches of 100 or less
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i:i + batch_size]
                try:
                    index.upsert(vectors=batch, namespace=namespace)
                except Exception as e:
                    print(f"Error uploading batch {i//batch_size} for {file.filename}: {e}")
                    failed_chunks += len(batch)
                    successful_chunks -= len(batch)
        
        return {
            "success": True,
            "filename": file.filename,
            "total_chunks_created": len(chunks_with_metadata),
            "successful_uploads": successful_chunks,
            "failed_uploads": failed_chunks,
            "file_size_bytes": len(content)
        }
        
    except Exception as e:
        return {
            "success": False,
            "filename": file.filename,
            "error": f"Failed to process file: {str(e)}"
        }

@router.post("/upload")
@limiter.limit("50/minute")
async def upload_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    chunk_size: int = Form(200, description="Size of each chunk in tokens"),
    overlap: int = Form(50, description="Overlap between chunks in tokens"),
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload .txt and .md files with dynamic chunking strategy and upload to Pinecone index.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate chunking parameters
        if chunk_size < 10 or chunk_size > 1000:
            raise HTTPException(status_code=400, detail="chunk_size must be between 10 and 1000")
        
        if overlap < 0 or overlap >= chunk_size:
            raise HTTPException(status_code=400, detail="overlap must be between 0 and chunk_size")
        
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        namespace = "ai_school_kb"  # Using the namespace for reranking
        
        # Get Pinecone index
        index = pc.Index(index_name)
        
        # Get JWT token for embedding service
        jwt = request.cookies.get("jwt") if request else None
        
        # Process each file
        file_results = []
        total_successful_uploads = 0
        total_failed_uploads = 0
        total_chunks_created = 0
        
        for file in files:
            print(f"Processing file: {file.filename}")
            result = await process_single_file(file, jwt, index, namespace, chunk_size, overlap)
            file_results.append(result)
            
            if result["success"]:
                total_successful_uploads += result["successful_uploads"]
                total_failed_uploads += result["failed_uploads"]
                total_chunks_created += result["total_chunks_created"]
        
        # Return format depends on whether it's single or multiple files
        if len(files) == 1:
            # Single file - return the result directly for backward compatibility
            return file_results[0]
        else:
            # Multiple files - return aggregate results
            return {
                "success": True,
                "files_processed": len(files),
                "file_results": file_results,
                "total_chunks_created": total_chunks_created,
                "total_successful_uploads": total_successful_uploads,
                "total_failed_uploads": total_failed_uploads,
                "namespace": namespace,
                "chunk_size": chunk_size,
                "overlap": overlap
            }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to upload files: {str(e)}"
        }

# @router.post("/upload-single")
# @limiter.limit("50/minute")
# async def upload_single_file(
#     file: UploadFile = File(..., description="Single file to upload"),
#     chunk_size: int = Form(200, description="Size of each chunk in tokens"),
#     overlap: int = Form(50, description="Overlap between chunks in tokens"),
#     decoded_jwt: jwt_dependency = None,
#     request: Request = None
# ):
#     """
#     Upload a single .txt or .md file with dynamic chunking strategy and upload to Pinecone index.
#     This endpoint is for backward compatibility with existing frontend implementations.
#     """
#     try:
#         # Validate chunking parameters
#         if chunk_size < 10 or chunk_size > 1000:
#             raise HTTPException(status_code=400, detail="chunk_size must be between 10 and 1000")
        
#         if overlap < 0 or overlap >= chunk_size:
#             raise HTTPException(status_code=400, detail="overlap must be between 0 and chunk_size")
        
#         # Get the index name from environment variables
#         index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
#         namespace = "reranking"  # Using the namespace for reranking
        
#         # Get Pinecone index
#         index = pc.Index(index_name)
        
#         # Get JWT token for embedding service
#         jwt = request.cookies.get("jwt") if request else None
        
#         # Process the single file
#         result = await process_single_file(file, jwt, index, namespace, chunk_size, overlap)
        
#         return result
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         return {
#             "success": False,
#             "error": f"Failed to upload file: {str(e)}"
#        } 

@router.post("/upload-text-single")
@limiter.limit("100/minute")
async def upload_file_to_gcs(
    file: UploadFile = File(..., description="Single file to upload"),
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a single file to Google Cloud Storage and queue it for async processing.
    The file will be processed (chunked and uploaded to Pinecone) asynchronously.
    This endpoint follows the same design as the similaritySearch module.
    """
    try:
        if not decoded_jwt:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate file type - support .txt and .md files for reranking
        if not file.filename.endswith(('.txt', '.md')):
            return {
                "success": False,
                "error": "Only .txt and .md files are supported for reranking"
            }
        
        # Initialize reranking upload service
        upload_service = RerankingUploadService()
        namespace = "ai_school_kb"
        
        print("decoded_jwt", decoded_jwt)

        # Upload file to GCS and publish to Pub/Sub
        result = await upload_service.upload_file_and_publish(
            file=file,
            user_id=str(decoded_jwt.get('id')),
            user_email=str(decoded_jwt.get('email')),
            namespace=namespace,
            jwt=request.cookies.get("jwt") if request else None
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to upload file: {str(e)}"
        } 