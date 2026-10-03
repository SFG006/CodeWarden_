import asyncio
import websockets
import requests
import json


async def run_fast_code():
    # 1. Define a script that runs VERY fast
    payload = {
  "language": "python",
  "code": "class Node:\n    def __init__(self, data):\n        self.data = data\n        self.next = None\n\n\ndef merge_lists(a, b):\n    dummy = Node(0)\n    tail = dummy\n\n    while a and b:\n        if a.data <= b.data:\n            tail.next = a\n            a = a.next\n        else:\n            tail.next = b\n            b = b.next\n        tail = tail.next\n\n    tail.next = a if a else b\n    return dummy.next\n\n\ndef print_list(head):\n    while head:\n        print(head.data, end=' ')\n        head = head.next\n    print()\n\n\na = Node(1)\na.next = Node(3)\na.next.next = Node(5)\n\nb = Node(2)\nb.next = Node(4)\nb.next.next = Node(6)\n\nresult = merge_lists(a, b)\nprint('Merged list:')\nprint_list(result)"
}

    # 2. Submit the code via HTTP POST
    print("Submitting job...")
    response = requests.post("http://localhost:8000/execute", json=payload)
    job_id = response.json()["job_id"]
    print(f"Job queued: {job_id}\n")

    # 3. INSTANTLY connect to the WebSocket stream
    ws_url = f"ws://localhost:8000/stream/{job_id}"

    try:
        # We are connecting in milliseconds, catching the broadcast as it starts
        async with websockets.connect(ws_url) as websocket:
            while True:
                message = await websocket.recv()
                print(message, end="", flush=True)
    except websockets.exceptions.ConnectionClosed:
        print("\n\nStream closed cleanly.")


if __name__ == "__main__":
    asyncio.run(run_fast_code())