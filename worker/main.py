import docker
from docker.errors import ImageNotFound, DockerException
import redis
import json
import time

# Connect to Redis and Docker
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError:
    print("FATAL: Could not connect to Redis. Ensure Docker Desktop is running the Redis container.")
    exit(1)

try:
    docker_client = docker.from_env()
except Exception as e:
    print(f"FATAL: Could not connect to Docker Daemon. {e}")
    exit(1)

def execute_sandbox(code: str) -> dict:
    """Worker code"""
    container = None
    try:
        # Spin up the sandbox with strict hardware and network limitations
        container = docker_client.containers.run(
            image="python:3.9-alpine",
            command=["timeout", "3", "python", "-uc", code],  # 'timeout 3' kills script if it hangs
            detach=True,
            mem_limit="128m",
            init=True,
            memswap_limit="128m",  # 128 MB total memory, no swap space
            cpu_period=100000,
            cpu_quota=50000,  # Cap at 50% of a single CPU core
            network_mode="none",  # Disable internet access
            user="1000"  # Run as non-root unprivileged user
        )

        result = container.wait()

        # Capture stdout and stderr
        output = container.logs().decode("utf-8").strip()
        # Exit code 143 (SIGTERM) is standard when 'timeout' kills a process
        is_timeout = result["StatusCode"] == 143

        return {
            "status": "timeout" if is_timeout else "success" if result["StatusCode"] == 0 else "error",
            "exit_code": result["StatusCode"],
            "output": output if output else "No output generated."
        }

    except ImageNotFound:

        return {
            "status": "system_error",
            "exit_code": -1,
            "output": "Docker image 'python:3.9-alpine' not found."
        }

    except DockerException as e:

        return {"status": "system_error",
                "exit_code": -1,
                "output": f"Docker engine error: {str(e)}"
        }

    except Exception as e:

        return {"status": "system_error",
                "exit_code": -1,
                "output": f"Worker execution failed: {str(e)}"
        }

    finally:
        # Always clean up container to prevent leaks
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass

def main():
    print("Worker daemon started. Waiting for jobs on 'code_execution_queue'...")

    while True:
        try:

            # blpop (Block Left Pop) pauses the loop efficiently until a job arrives.
            # worker isn't continuously checking the queue as we didn't use lpop which will cause long polling
            # The '0' means wait indefinitely without timing out.
            _, raw_job = redis_client.blpop(
                "code_execution_queue",
                0
            )

            job = json.loads(raw_job)
            job_id = job["job_id"]
            code = job["code"]

            print(f"[{job_id}] Job pulled. Executing...")

            # Update status in Redis so the client knows it's no longer queued
            job["status"] = "processing" # only changes dict in memory,

            redis_client.set(                   # to change in redis dict too
                f"job_status:{job_id}", # key
                json.dumps(job)         # value
            )

            # Run the Docker container
            execution_result = execute_sandbox(code)

            # Merge the results and update Redis with the final status
            job.update(execution_result)
            redis_client.set(  # to change in redis dict too
                f"job_status:{job_id}",  # key
                json.dumps(job)  # value
            )
            print(f"[{job_id}] Finished. Status: {job['status']}")


        except redis.RedisError as e:
            print(f"Redis connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5) #pause the worker for a 5sec before it tries again

        except Exception as e:
            print(f"Worker encountered an unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()


