
import os
os.environ["AI_PROVIDER"] = "minimax"
# Validating import
try:
    from web_app import app
    print("Startup Import Successful")
except Exception as e:
    print(f"Startup Failed: {e}")
