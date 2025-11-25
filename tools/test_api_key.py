#!/usr/bin/env python3
"""Quick test to check if API key is working"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from api.utils import load_environment, ensure_env

def test_api_key():
    """Test API key with a simple call"""
    try:
        # Load environment
        load_environment()
        ensure_env("GOOGLE_API_KEY")
        print("✓ Environment loaded successfully")

        # Create client
        client = genai.Client()
        print("✓ Client created successfully")

        # Make a simple API call
        print("\nTesting API call...")
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello in one word"
        )

        # Check response
        if hasattr(resp, "text") and resp.text:
            result = resp.text
        else:
            result = str(resp)

        print(f"✓ API call successful!")
        print(f"Response: {result}")
        return True

    except Exception as e:
        error_str = str(e)
        print(f"✗ API call failed!")
        print(f"Error: {error_str}")

        if "429" in error_str or "quota" in error_str.lower():
            print("\n⚠️  QUOTA EXCEEDED - This API key has reached its usage limit")
        elif "401" in error_str or "invalid" in error_str.lower():
            print("\n⚠️  INVALID API KEY - The key may be incorrect or revoked")
        elif "403" in error_str or "forbidden" in error_str.lower():
            print("\n⚠️  PERMISSION DENIED - The key doesn't have access to this API")

        return False

if __name__ == "__main__":
    test_api_key()
