#!/usr/bin/env python3
import requests
import json

def simple_test():
    # Test health endpoint
    try:
        print("Testing health endpoint...")
        response = requests.get("http://localhost:8000/")
        print(f"Health: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")

    # Test parse with a simple approach
    try:
        print("\nTesting parse endpoint...")
        with open("samples/resume.pdf", "rb") as f:
            files = {"file": ("resume.pdf", f, "application/pdf")}
            response = requests.post("http://localhost:8000/parse", files=files, timeout=30)

        print(f"Parse: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {list(data.keys())}")
        else:
            print(f"Error response: {response.text}")

    except Exception as e:
        print(f"Parse test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_test()