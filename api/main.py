import uuid
import json
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="CodeWarden API"
)

# Connect to Redis
try:
    redis_client = redis.Redis(host='localhost',
                               port=6379,
                               db=0,
                               decode_responses=True
    )
    redis_client.ping() # Test the connection immediately

except redis.ConnectionError:
    redis_client = None

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"

@app.post("/execute")
def submit_code(payload: ExecuteRequest):
    if payload.language != "python":
        raise HTTPException(status_code=400, detail="Only Python is supported for NOW")
    
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis broker is not accessible.")

    # 1. Generate a unique ID for this execution
    job_id = str(uuid.uuid4())

    # 2. Package the job details
    job_data = {
        "job_id": job_id,
        "code": payload.code,
        "language": payload.language,
        "status": "queued"
    }

    try:
        # 3. Save initial status so the user can query it via GET /status
        redis_client.set(
            f"job_status:{job_id}",
            json.dumps(job_data)
        )

        # 4. Push the job to the back of the queue (rpush = Right Push)
        redis_client.rpush(
            "code_execution_queue",
            json.dumps(job_data)
        )

    except redis.RedisError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue job: {str(e)}"
        )

    # 5. Return immediately
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job submitted successfully"
    }

@app.get("/status/{job_id}")
def get_status(job_id: str):
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis broker is not accessible.")

    # Fetch the current state of the job from Redis
    result = redis_client.get(f"job_status:{job_id}")

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    return json.loads(result)
