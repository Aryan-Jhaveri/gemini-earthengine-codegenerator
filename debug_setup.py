
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("--- DEBUGGING SETUP ---")

# 1. Check Google GenAI
try:
    from google import genai
    print("✅ google-genai imported successfully")
except ImportError as e:
    print(f"❌ Failed to import google-genai: {e}")

# 2. Check Environment Variables
project = os.getenv("GOOGLE_CLOUD_PROJECT")
print(f"ℹ️ GOOGLE_CLOUD_PROJECT: {project}")

# 3. Check Earth Engine
import ee
try:
    if project:
        print(f"Attempting ee.Initialize(project='{project}')")
        ee.Initialize(project=project)
    else:
        print("Attempting ee.Initialize() (no project)")
        ee.Initialize()
    print("✅ Earth Engine Initialized")
except Exception as e:
    print(f"❌ Earth Engine Initialization Failed: {e}")
    # Try Auth
    try:
        print("Attempting ee.Authenticate() + Initialize()...")
        ee.Authenticate()
        ee.Initialize(project=project) if project else ee.Initialize()
        print("✅ Earth Engine Initialized after Auth")
    except Exception as e2:
        print(f"❌ Earth Engine Auth/Init Failed: {e2}")

print("--- END DEBUG ---")
