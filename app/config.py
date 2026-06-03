import os
from dotenv import load_dotenv

# Load .env file and override existing environment variables
load_dotenv(override=True)

SMARTY_AUTH_ID = os.getenv("SMARTY_AUTH_ID")
SMARTY_AUTH_TOKEN = os.getenv("SMARTY_AUTH_TOKEN")

# Debug logging for troubleshooting credentials
print(f"\n--- DEBUG: CREDENTIAL CHECK ---")
print(f"SMARTY_AUTH_ID:     {repr(SMARTY_AUTH_ID)} (len={len(SMARTY_AUTH_ID) if SMARTY_AUTH_ID else 0})")
print(f"SMARTY_AUTH_TOKEN:  {repr(SMARTY_AUTH_TOKEN)} (len={len(SMARTY_AUTH_TOKEN) if SMARTY_AUTH_TOKEN else 0})")
print(f"--------------------------------\n")

if not SMARTY_AUTH_ID:
    raise ValueError("SMARTY_AUTH_ID is missing from the environment configuration.")

if not SMARTY_AUTH_TOKEN:
    raise ValueError("SMARTY_AUTH_TOKEN is missing from the environment configuration.")
