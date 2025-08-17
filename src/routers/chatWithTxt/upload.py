from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import json
import hashlib
import time
import asyncio
from typing import List
from src.core.clients import pc
from src.deps import jwt_dependency
from src.services import fetch_embedding
import tiktoken

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

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

async def process_chunk_with_embedding(chunk: str, chunk_index: int, filename: str, jwt: str) -> dict:
    """
    Process a single chunk by generating its embedding and preparing vector data.
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
        
        # Prepare vector data
        vector_data = {
            "id": chunk_id,
            "values": embedding_values,
            "metadata": {
                "filename": filename,
                "chunk_id": chunk_index,
                "content": chunk,
                "chunk_size_tokens": len(chunk.split()),  # Approximate token count
                "upload_timestamp": str(int(time.time() * 1000))
            }
        }
        
        return vector_data
    except Exception as e:
        print(f"Error processing chunk {chunk_index}: {e}")
        return None

@router.post("/upload")
@limiter.limit("50/minute")
async def upload_file(
    file: UploadFile = File(...),
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a .txt file, chunk it into 200-token pieces, and upload to Pinecone index.
    """
    try:
        # Validate file type
        if not file.filename.endswith('.txt'):
            raise HTTPException(status_code=400, detail="Only .txt files are supported")
        
        # Read file content
        content = await file.read()
        text_content = content.decode('utf-8')
        
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Chunk the text into 200-token pieces
        chunks = chunk_text_by_tokens(text_content, chunk_size=200, overlap=50)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No valid chunks created from file")
        
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        namespace = "chat_with_txt"
        
        # Get Pinecone index
        index = pc.Index(index_name)
        
        # Get JWT token for embedding service
        jwt = request.cookies.get("jwt") if request else None
        
        # Process chunks in parallel
        print(f"Processing {len(chunks)} chunks in parallel...")
        
        # Create tasks for parallel processing
        tasks = []
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i} of {len(chunks)}")
            task = process_chunk_with_embedding(chunk, i, file.filename, jwt)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        vectors_to_upsert = []
        successful_chunks = 0
        failed_chunks = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception processing chunk {i}: {result}")
                failed_chunks += 1
            elif result is not None:
                # Add total_chunks to metadata
                result["metadata"]["total_chunks"] = len(chunks)
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
                    print(f"Error uploading batch {i//batch_size}: {e}")
                    failed_chunks += len(batch)
                    successful_chunks -= len(batch)
        
        return {
            "success": True,
            "filename": file.filename,
            "total_chunks_created": len(chunks),
            "successful_uploads": successful_chunks,
            "failed_uploads": failed_chunks,
            "namespace": namespace,
            "file_size_bytes": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to upload file: {str(e)}",
            "filename": file.filename if file else "unknown"
        } 