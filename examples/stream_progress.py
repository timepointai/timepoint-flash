#!/usr/bin/env python3
"""
TIMEPOINT Flash - Server-Sent Events (SSE) Streaming Example

Shows how to watch generation progress in real-time using SSE.

Requirements:
    pip install requests sseclient-py

Just run: python3 stream_progress.py
"""

import requests
import json
import sys

try:
    from sseclient import SSEClient
except ImportError:
    print("❌ Missing dependency: sseclient-py")
    print("   Install with: pip install sseclient-py")
    sys.exit(1)


# Server URL
API_BASE = "http://localhost:8000"


def generate_timepoint(query: str, email: str = "dev@example.com") -> dict:
    """Create a new timepoint and return session data."""

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
    print(f"   Slug: {data['slug']}\n")

    return data


def stream_progress(session_id: str) -> str | None:
    """
    Stream progress updates via SSE.

    Returns the final slug on success, None on error.
    """

    print("📡 Streaming progress...\n")

    url = f"{API_BASE}/api/timepoint/status/{session_id}"

    try:
        response = requests.get(url, stream=True, headers={"Accept": "text/event-stream"})
        response.raise_for_status()

        client = SSEClient(response)

        for event in client.events():
            event_type = event.event  # 'progress', 'complete', 'error'
            data = json.loads(event.data)

            if event_type == "progress":
                agent = data.get("agent", "unknown")
                message = data.get("message", "")
                progress = data.get("progress", 0)

                # Pretty progress bar
                bar_length = 30
                filled = int(bar_length * progress / 100)
                bar = "█" * filled + "░" * (bar_length - filled)

                print(f"[{bar}] {progress:3d}% | {agent:12s} | {message}")

            elif event_type == "complete":
                slug = data.get("slug")
                print(f"\n✅ Complete! Slug: {slug}")
                return slug

            elif event_type == "error":
                error = data.get("error", "Unknown error")
                print(f"\n❌ Error: {error}")
                return None

    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error. Is the server running?")
        return None
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


def get_timepoint_details(slug: str) -> dict:
    """Fetch complete timepoint data."""

    response = requests.get(f"{API_BASE}/api/timepoint/details/{slug}")
    response.raise_for_status()
    return response.json()


def main():
    """Example: generate → stream progress → fetch results."""

    print("\n" + "🍌" * 30)
    print("TIMEPOINT Flash - SSE Streaming Example")
    print("🍌" * 30 + "\n")

    # Step 1: Generate a timepoint
    query = "Ancient Rome forum, summer 50 BCE, midday"
    result = generate_timepoint(query)

    if not result:
        return

    session_id = result["session_id"]

    # Step 2: Stream progress in real-time
    slug = stream_progress(session_id)

    if not slug:
        print("\n❌ Generation failed")
        return

    # Step 3: Fetch final results
    print(f"\n📥 Fetching details...")
    timepoint = get_timepoint_details(slug)

    print("\n" + "=" * 60)
    print(f"🎬 {timepoint['slug']}")
    print("=" * 60)
    print(f"Query:        {timepoint['input_query']}")
    print(f"Year:         {timepoint.get('year', 'Unknown')}")
    print(f"Season:       {timepoint.get('season', 'Unknown')}")
    print(f"Image URL:    {timepoint.get('image_url', 'N/A')}")
    print(f"Characters:   {len(timepoint.get('character_data_json', []))}")
    print(f"Processing:   {timepoint.get('processing_time_ms', 0) / 1000:.1f}s")
    print("=" * 60)

    print("\n✨ Done! Visit: http://localhost:8000/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled")
