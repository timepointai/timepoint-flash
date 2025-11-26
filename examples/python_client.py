#!/usr/bin/env python3
"""
TIMEPOINT Flash - Python Client Example

Simple example showing how to:
1. Generate a timepoint
2. Wait for completion
3. Fetch the results

Just run: python3 python_client.py
"""

import requests
import time
import json
from typing import Dict, Any

# Server URL (default: localhost:8000)
API_BASE = "http://localhost:8000"


def generate_timepoint(query: str, email: str = "dev@example.com") -> Dict[str, Any]:
    """Create a new timepoint generation request."""

    print(f"🚀 Generating timepoint: '{query}'")

    response = requests.post(
        f"{API_BASE}/api/timepoint/create",
        json={
            "input_query": query,
            "requester_email": email
        }
    )

    if response.status_code == 429:
        print("❌ Rate limit exceeded!")
        print(response.json()["detail"])
        return None

    response.raise_for_status()
    data = response.json()

    print(f"✅ Started: session_id={data['session_id']}")
    print(f"   Slug: {data['slug']}")

    return data


def check_status(slug: str) -> Dict[str, Any]:
    """Check the current status of a timepoint (quick check, no SSE)."""

    response = requests.get(f"{API_BASE}/api/timepoint/check/{slug}")
    response.raise_for_status()
    return response.json()


def wait_for_completion(slug: str, timeout: int = 120, poll_interval: int = 5) -> bool:
    """Poll the status endpoint until complete or timeout."""

    print(f"\n⏳ Waiting for completion (timeout: {timeout}s)...")

    elapsed = 0
    while elapsed < timeout:
        status_data = check_status(slug)
        status = status_data.get("status")
        progress = status_data.get("progress", 0)

        print(f"   [{elapsed}s] Status: {status} - Progress: {progress}%")

        if status == "complete":
            print("✅ Complete!")
            return True

        if status == "failed":
            error = status_data.get("error", "Unknown error")
            print(f"❌ Failed: {error}")
            return False

        time.sleep(poll_interval)
        elapsed += poll_interval

    print(f"⏰ Timeout after {timeout}s")
    return False


def get_timepoint_details(slug: str) -> Dict[str, Any]:
    """Fetch complete timepoint data."""

    print(f"\n📥 Fetching details for: {slug}")

    response = requests.get(f"{API_BASE}/api/timepoint/details/{slug}")
    response.raise_for_status()
    return response.json()


def get_feed(limit: int = 5) -> Dict[str, Any]:
    """Get the latest timepoints."""

    print(f"\n📋 Fetching feed (limit={limit})...")

    response = requests.get(f"{API_BASE}/api/feed?limit={limit}")
    response.raise_for_status()
    return response.json()


def print_timepoint_summary(tp: Dict[str, Any]):
    """Pretty-print a timepoint summary."""

    print("\n" + "=" * 60)
    print(f"🎬 {tp['slug']}")
    print("=" * 60)
    print(f"Query:        {tp['input_query']}")
    print(f"Year:         {tp.get('year', 'Unknown')}")
    print(f"Season:       {tp.get('season', 'Unknown')}")
    print(f"Location:     {tp.get('location', 'Unknown')}")
    print(f"Image URL:    {tp.get('image_url', 'N/A')}")
    print(f"Characters:   {len(tp.get('character_data_json', []))}")
    print(f"Dialog lines: {len(tp.get('dialog_json', []))}")
    print(f"Processing:   {tp.get('processing_time_ms', 0) / 1000:.1f}s")
    print("=" * 60)


def main():
    """Example workflow: generate → wait → fetch."""

    print("\n" + "🍌" * 30)
    print("TIMEPOINT Flash - Python Client Example")
    print("🍌" * 30 + "\n")

    # Step 1: Generate a timepoint
    query = "Medieval marketplace, London 1250, winter morning"
    result = generate_timepoint(query)

    if not result:
        return

    slug = result["slug"]

    # Step 2: Wait for completion (polls every 5 seconds)
    success = wait_for_completion(slug, timeout=120, poll_interval=5)

    if not success:
        print("\n❌ Generation failed or timed out")
        return

    # Step 3: Fetch the complete data
    timepoint = get_timepoint_details(slug)
    print_timepoint_summary(timepoint)

    # Optional: Show characters
    if timepoint.get("character_data_json"):
        print("\n👥 Characters:")
        for char in timepoint["character_data_json"]:
            print(f"  - {char.get('name', 'Unknown')}: {char.get('role', 'N/A')}")

    # Optional: Show dialog
    if timepoint.get("dialog_json"):
        print("\n💬 Dialog:")
        for line in timepoint["dialog_json"][:3]:  # Show first 3 lines
            print(f"  {line.get('character', '???')}: \"{line.get('text', '')}\"")

    print("\n✨ Done! Visit the gallery: http://localhost:8000/")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server")
        print("   Make sure the server is running: ./tp serve")
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
