import asyncio
import websockets

async def main():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MmExNTEzMy1iNDhjLTQ4YTMtYThjMi1lMDViMjRhODcyZmIiLCJleHAiOjE3ODM3OTYwMTR9.SkDvI2luHFGT28putgjuG_JEa7I_lxb7hhS7Zt3jz18"
    uri = f"ws://localhost:8000/ws/123?token={token}"
    async with websockets.connect(uri) as ws:
        await ws.send("hello from authenticated client")
        response = await ws.recv()
        print("Received:", response)

asyncio.run(main())