#!/usr/bin/env python3
"""
Script to test the calling agent by making a test call
"""

import os
import sys
import asyncio
import httpx

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        print(f"Health: {response.json()}")
        return response.status_code == 200


async def test_ready():
    """Test readiness endpoint"""
    print("\nTesting readiness endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/ready")
        print(f"Ready: {response.json()}")
        return response.json()


async def initiate_test_call(phone_number: str):
    """Initiate a test call"""
    print(f"\nInitiating test call to {phone_number}...")

    payload = {
        "phone_number": phone_number,
        "system_prompt": """You are a friendly AI assistant making a test call.
Your purpose is to:
1. Greet the person politely
2. Explain this is a test call from the AI calling system
3. Ask if they have a moment to verify the connection quality
4. Thank them and end the call

Keep the conversation brief and professional.""",
        "greeting_message": "Hello! This is a test call from the AI calling system. Is this a good time to do a quick connection test?",
        "metadata": {
            "test": True,
            "purpose": "connection_test"
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/api/v1/calls/initiate",
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print(f"Call initiated successfully!")
            print(f"  Call ID: {data.get('call_id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Twilio SID: {data.get('twilio_call_sid')}")
            print(f"  Ultravox ID: {data.get('ultravox_call_id')}")
            return data
        else:
            print(f"Failed to initiate call: {response.status_code}")
            print(f"Error: {response.text}")
            return None


async def get_call_status(call_id: str):
    """Get the status of a call"""
    print(f"\nGetting status for call {call_id}...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/v1/calls/{call_id}")

        if response.status_code == 200:
            data = response.json()
            print(f"Call Status: {data.get('status')}")
            return data
        else:
            print(f"Failed to get call status: {response.status_code}")
            return None


async def list_active_calls():
    """List all active calls"""
    print("\nListing active calls...")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/v1/calls/active/list")

        if response.status_code == 200:
            data = response.json()
            print(f"Active calls: {data.get('count')}")
            for call in data.get('active_calls', []):
                print(f"  - {call.get('call_id')}: {call.get('status')}")
            return data
        else:
            print(f"Failed to list calls: {response.status_code}")
            return None


async def end_call(call_id: str):
    """End a call"""
    print(f"\nEnding call {call_id}...")

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}/api/v1/calls/{call_id}/end")

        if response.status_code == 200:
            print("Call ended successfully")
            return True
        else:
            print(f"Failed to end call: {response.status_code}")
            return False


async def main():
    """Main test function"""
    print("=" * 60)
    print("Calling Agent Test Script")
    print("=" * 60)

    # Test health
    if not await test_health():
        print("Server is not healthy. Exiting.")
        return

    # Test readiness
    ready_status = await test_ready()
    if ready_status.get("status") != "ready":
        print("Warning: Server is not fully ready")
        print(f"Checks: {ready_status.get('checks')}")

    # Check if phone number was provided
    if len(sys.argv) < 2:
        print("\nUsage: python test_call.py <phone_number>")
        print("Example: python test_call.py +14155551234")
        print("\nSkipping call test. Only running health checks.")
        return

    phone_number = sys.argv[1]

    # Validate phone number format
    if not phone_number.startswith("+"):
        print("Error: Phone number must be in E.164 format (e.g., +14155551234)")
        return

    # Initiate test call
    call_result = await initiate_test_call(phone_number)

    if call_result:
        call_id = call_result.get("call_id")

        # Wait a bit and check status
        print("\nWaiting 5 seconds before checking status...")
        await asyncio.sleep(5)

        await get_call_status(call_id)
        await list_active_calls()

        # Ask if user wants to end the call
        print("\nThe call is in progress. It will end naturally when completed.")
        print("You can also end it manually using the API:")
        print(f"  POST {API_BASE_URL}/api/v1/calls/{call_id}/end")


if __name__ == "__main__":
    asyncio.run(main())
