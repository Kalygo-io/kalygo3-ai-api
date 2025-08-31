from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks
from pydantic import BaseModel
import replicate
from src.deps import jwt_dependency
import os
from src.core.clients import pc
import asyncio
import json
import requests
import threading
import uuid
from starlette.responses import StreamingResponse

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

class Query(BaseModel):
    text: str

# Global cancellation tracking
cancellation_flags = {}

def get_cancellation_flag(request_id: str):
    """Get or create a cancellation flag for a request"""
    if request_id not in cancellation_flags:
        cancellation_flags[request_id] = threading.Event()
    return cancellation_flags[request_id]

def set_cancellation_flag(request_id: str):
    """Set the cancellation flag for a request"""
    if request_id in cancellation_flags:
        cancellation_flags[request_id].set()

def clear_cancellation_flag(request_id: str):
    """Clear the cancellation flag for a request"""
    if request_id in cancellation_flags:
        cancellation_flags[request_id].clear()
        del cancellation_flags[request_id]

def is_cancelled(request_id: str) -> bool:
    """Check if a request has been cancelled"""
    return get_cancellation_flag(request_id).is_set()

async def monitor_request_cancellation(request: Request, request_id: str):
    """Background task to monitor request cancellation"""
    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                print(f"Client disconnected detected for request {request_id}")
                set_cancellation_flag(request_id)
                break
            
            # Check if cancellation flag is set
            if is_cancelled(request_id):
                print(f"Cancellation flag set for request {request_id}")
                break
            
            await asyncio.sleep(0.1)  # Check every 100ms
    except Exception as e:
        print(f"Error in request cancellation monitor: {e}")
    finally:
        clear_cancellation_flag(request_id)

async def cancel_replicate_prediction(prediction_id: str):
    """Cancel a Replicate prediction using their cancel endpoint"""
    try:
        print(f"Cancelling Replicate prediction: {prediction_id}")
        
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            print("REPLICATE_API_TOKEN not found")
            return False
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}/cancel"
        
        response = requests.post(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"Successfully cancelled Replicate prediction {prediction_id}")
            return True
        else:
            print(f"Failed to cancel Replicate prediction {prediction_id}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error cancelling Replicate prediction: {str(e)}")
        return False

async def run_replicate_with_cancellation(request: Request, text_input: str, request_id: str):
    """Run Replicate with cancellation support using HTTP API"""
    prediction_id = None
    
    try:
        print(f"Starting Replicate prediction for: {text_input}")
        
        # Get API token
        api_token = os.getenv("REPLICATE_API_TOKEN")
        if not api_token:
            raise HTTPException(status_code=500, detail="REPLICATE_API_TOKEN not configured")
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        # Create prediction
        prediction_data = {
            "version": "daanelson/imagebind:0383f62e173dc821ec52663ed22a076d9c970549c209666ac3db181618b7a304",
            "input": {
                "modality": "text",
                "text_input": text_input,
            }
        }
        
        # Create the prediction
        create_response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json=prediction_data,
            timeout=30
        )
        
        if create_response.status_code != 201:
            raise HTTPException(status_code=500, detail=f"Failed to create Replicate prediction: {create_response.text}")
        
        prediction = create_response.json()
        prediction_id = prediction.get('id')
        
        if not prediction_id:
            raise HTTPException(status_code=500, detail="No prediction ID returned from Replicate")
        
        print(f"Created Replicate prediction: {prediction_id}")
        
        # Poll for completion with cancellation checks
        poll_count = 0
        while True:
            poll_count += 1
            print(f"Polling prediction {prediction_id} - attempt {poll_count}")
            
            # Check if request was cancelled (multiple ways)
            is_disconnected = await request.is_disconnected()
            is_cancelled_flag = is_cancelled(request_id)
            print(f"Client disconnected check (attempt {poll_count}): {is_disconnected}")
            print(f"Cancellation flag check (attempt {poll_count}): {is_cancelled_flag}")
            
            if is_disconnected or is_cancelled_flag:
                print(f"Cancellation detected, cancelling prediction {prediction_id}")
                await cancel_replicate_prediction(prediction_id)
                raise HTTPException(status_code=499, detail="Request cancelled")
            
            # Get prediction status
            status_response = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers=headers,
                timeout=10
            )
            
            if status_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Failed to get prediction status: {status_response.text}")
            
            prediction_status = status_response.json()
            status = prediction_status.get('status')
            
            print(f"Prediction {prediction_id} status: {status}")
            
            if status == 'succeeded':
                output = prediction_status.get('output')
                if not output:
                    raise HTTPException(status_code=500, detail="No output returned from Replicate")
                return output
            elif status == 'failed':
                error = prediction_status.get('error', 'Unknown error')
                raise HTTPException(status_code=500, detail=f"Replicate prediction failed: {error}")
            elif status == 'canceled':
                raise HTTPException(status_code=499, detail="Prediction was canceled")
            
            # Check again AFTER the API call
            is_disconnected = await request.is_disconnected()
            is_cancelled_flag = is_cancelled(request_id)
            print(f"Client disconnected check after API call (attempt {poll_count}): {is_disconnected}")
            print(f"Cancellation flag check after API call (attempt {poll_count}): {is_cancelled_flag}")
            
            if is_disconnected or is_cancelled_flag:
                print(f"Cancellation detected after API call, cancelling prediction {prediction_id}")
                await cancel_replicate_prediction(prediction_id)
                raise HTTPException(status_code=499, detail="Request cancelled")
            
            # Wait before polling again
            print(f"Waiting 0.5 seconds before next poll...")
            await asyncio.sleep(0.5)
        
    except asyncio.CancelledError:
        print(f"asyncio.CancelledError caught - cancelling prediction {prediction_id}")
        if prediction_id:
            await cancel_replicate_prediction(prediction_id)
        raise
    except HTTPException:
        # Try to cancel prediction if request was cancelled
        if prediction_id:
            is_disconnected = await request.is_disconnected()
            is_cancelled_flag = is_cancelled(request_id)
            print(f"HTTPException caught, checking disconnection: {is_disconnected}")
            print(f"HTTPException caught, checking cancellation flag: {is_cancelled_flag}")
            if is_disconnected or is_cancelled_flag:
                print(f"Cancelling prediction {prediction_id} due to HTTPException and cancellation")
                await cancel_replicate_prediction(prediction_id)
        raise
    except Exception as e:
        print(f"Error in Replicate call: {str(e)}")
        # Try to cancel prediction on error
        if prediction_id:
            print(f"Cancelling prediction {prediction_id} due to exception")
            await cancel_replicate_prediction(prediction_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {str(e)}")

@router.post("/media-assets/query")
@limiter.limit("10/minute")
async def media_library(request: Request, response: Response, jwt: jwt_dependency, query: Query, background_tasks: BackgroundTasks):
    """
    Query media assets with proper AbortController support using streaming.
    This endpoint will detect client disconnection and cancel operations accordingly.
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    
    print(f"Received query: {query.text} (Request ID: {request_id})")
    
    # Start background task to monitor request cancellation
    background_tasks.add_task(monitor_request_cancellation, request, request_id)
    
    async def generate_response():
        try:
            # Phase 1: Send initial status
            yield json.dumps({"status": "starting", "message": "Generating embedding..."}) + "\n"
            
            # Check for cancellation before starting Replicate
            if await request.is_disconnected() or is_cancelled(request_id):
                print("Request cancelled before Replicate call")
                yield json.dumps({"status": "cancelled", "message": "Request cancelled"}) + "\n"
                return
            
            # Phase 2: Generate embedding with Replicate (with cancellation support)
            print(f"Generating ImageBind embedding for query: {query.text}")
            yield json.dumps({"status": "embedding", "message": "Calling Replicate API..."}) + "\n"
            
            # Use the cancellation-aware Replicate function
            output = await run_replicate_with_cancellation(request, query.text, request_id)
            
            # Check for cancellation after Replicate
            if await request.is_disconnected() or is_cancelled(request_id):
                print("Request cancelled after Replicate call")
                yield json.dumps({"status": "cancelled", "message": "Request cancelled after embedding"}) + "\n"
                return
            
            # Phase 3: Query Pinecone
            print(f"Replicate output received, querying Pinecone...")
            yield json.dumps({"status": "searching", "message": "Searching vector database..."}) + "\n"
            
            index_name = os.getenv("PINECONE_IMAGEBIND_1024_DIMS_INDEX")
            if not index_name:
                yield json.dumps({"status": "error", "message": "Pinecone index not configured"}) + "\n"
                return
                
            print(f"Using Pinecone index: {index_name}")
            index = pc.Index(index_name)
            
            # Run Pinecone query in executor
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, lambda: index.query(
                vector=output,
                top_k=3,
                include_values=False,
                include_metadata=True,
                namespace='media_assets'
            ))
            
            # Check for cancellation after Pinecone
            if await request.is_disconnected() or is_cancelled(request_id):
                print("Request cancelled after Pinecone query")
                yield json.dumps({"status": "cancelled", "message": "Request cancelled after search"}) + "\n"
                return
            
            # Phase 4: Process and return results
            print(f"Pinecone query results: {results}")
            yield json.dumps({"status": "processing", "message": "Processing results..."}) + "\n"
            
            final_results = []
            for r in results['matches']:
                final_results.append({'metadata': r['metadata'], 'score': r['score']})
            
            # Final result
            yield json.dumps({
                "status": "completed", 
                "results": final_results,
                "message": "Search completed successfully"
            }) + "\n"
            
        except asyncio.CancelledError:
            print("Request was cancelled (CancelledError) in generate_response")
            yield json.dumps({"status": "cancelled", "message": "Request was cancelled"}) + "\n"
        except Exception as e:
            print(f"Error in media query: {str(e)}")
            yield json.dumps({"status": "error", "message": f"Error: {str(e)}"}) + "\n"
        finally:
            # Clean up cancellation flag
            clear_cancellation_flag(request_id)
    
    return StreamingResponse(
        generate_response(), 
        media_type="application/x-ndjson"
    )

# Endpoint to manually trigger cancellation (for testing)
@router.post("/cancel-request/{request_id}")
async def cancel_request(request_id: str):
    """Manually trigger cancellation for a request (for testing)"""
    print(f"Manual cancellation requested for request ID: {request_id}")
    set_cancellation_flag(request_id)
    return {"message": "Cancellation signal sent", "request_id": request_id}

# Test endpoint to verify streaming cancellation works
@router.get("/test-streaming-cancellation")
async def test_streaming_cancellation(request: Request):
    """
    Test endpoint to verify that streaming cancellation detection works.
    """
    async def generate_test():
        try:
            for i in range(30):  # 30 seconds total
                # Check before yielding
                if await request.is_disconnected():
                    print(f"Client disconnected at iteration {i}")
                    yield json.dumps({"status": "cancelled", "iteration": i, "message": "Client disconnected"}) + "\n"
                    return
                
                # Send heartbeat
                yield json.dumps({"status": "running", "iteration": i, "message": f"Processing iteration {i}"}) + "\n"
                
                # Wait and check again
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    print(f"Client disconnected after sleep at iteration {i}")
                    yield json.dumps({"status": "cancelled", "iteration": i, "message": "Client disconnected after sleep"}) + "\n"
                    return
            
            # Completed successfully
            yield json.dumps({"status": "completed", "message": "All iterations completed"}) + "\n"
            
        except asyncio.CancelledError:
            print("Request cancelled via CancelledError")
            yield json.dumps({"status": "cancelled", "message": "Request cancelled via CancelledError"}) + "\n"
        except Exception as e:
            print(f"Error in test: {str(e)}")
            yield json.dumps({"status": "error", "message": f"Error: {str(e)}"}) + "\n"
    
    return StreamingResponse(
        generate_test(),
        media_type="application/x-ndjson"
    )

# Simple test endpoint to verify cancellation detection works
@router.get("/test-cancellation-detection")
async def test_cancellation_detection(request: Request):
    """
    Simple test endpoint to verify that cancellation detection works.
    """
    print("Test cancellation detection endpoint called")
    
    async def generate_simple_test():
        try:
            for i in range(10):  # 10 seconds total
                print(f"Test iteration {i + 1}/10")
                
                # Check disconnection
                is_disconnected = await request.is_disconnected()
                print(f"Iteration {i + 1}: is_disconnected = {is_disconnected}")
                
                if is_disconnected:
                    print(f"Cancellation detected at iteration {i + 1}")
                    yield json.dumps({"status": "cancelled", "iteration": i + 1, "message": "Cancellation detected"}) + "\n"
                    return
                
                # Send status
                yield json.dumps({"status": "running", "iteration": i + 1, "message": f"Running iteration {i + 1}"}) + "\n"
                
                # Wait
                await asyncio.sleep(1)
                
                # Check again after sleep
                is_disconnected = await request.is_disconnected()
                print(f"After sleep iteration {i + 1}: is_disconnected = {is_disconnected}")
                
                if is_disconnected:
                    print(f"Cancellation detected after sleep at iteration {i + 1}")
                    yield json.dumps({"status": "cancelled", "iteration": i + 1, "message": "Cancellation detected after sleep"}) + "\n"
                    return
            
            print("Test completed successfully")
            yield json.dumps({"status": "completed", "message": "Test completed successfully"}) + "\n"
            
        except asyncio.CancelledError:
            print("Test cancelled via CancelledError")
            yield json.dumps({"status": "cancelled", "message": "Test cancelled via CancelledError"}) + "\n"
        except Exception as e:
            print(f"Error in test: {str(e)}")
            yield json.dumps({"status": "error", "message": f"Error: {str(e)}"}) + "\n"
    
    return StreamingResponse(
        generate_simple_test(),
        media_type="application/x-ndjson"
    )
