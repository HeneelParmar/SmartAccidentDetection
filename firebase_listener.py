# firebase_listener.py
import firebase_admin
from firebase_admin import credentials, db
import joblib
import numpy as np
import time
import os
import json

# Read from environment variables
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
DATABASE_URL = os.getenv('DATABASE_URL')

if not SERVICE_ACCOUNT_JSON:
    raise ValueError("SERVICE_ACCOUNT_JSON environment variable is not set")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Parse JSON string and create credentials
try:
    # Strip whitespace
    json_str = SERVICE_ACCOUNT_JSON.strip()
    
    # Remove surrounding quotes if present (single or double)
    if (json_str.startswith('"') and json_str.endswith('"')) or \
       (json_str.startswith("'") and json_str.endswith("'")):
        json_str = json_str[1:-1]
    
    # Handle escaped JSON strings (common in environment variables)
    json_str = json_str.replace('\\"', '"').replace("\\'", "'")
    json_str = json_str.replace('\\n', '\n').replace('\\t', '\t')
    
    # Try to find the first { character in case there's a prefix
    first_brace = json_str.find('{')
    if first_brace > 0:
        json_str = json_str[first_brace:]
    
    # Find the last } character in case there's a suffix
    last_brace = json_str.rfind('}')
    if last_brace >= 0 and last_brace < len(json_str) - 1:
        json_str = json_str[:last_brace + 1]
    
    service_account_info = json.loads(json_str)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
except json.JSONDecodeError as e:
    print(f"ERROR: Failed to parse SERVICE_ACCOUNT_JSON: {str(e)}")
    print(f"First 200 chars: {SERVICE_ACCOUNT_JSON[:200] if SERVICE_ACCOUNT_JSON else 'None'}")
    print("Make sure SERVICE_ACCOUNT_JSON contains valid JSON without extra quotes or prefixes.")
    raise
except Exception as e:
    print(f"ERROR: Failed to initialize Firebase: {str(e)}")
    raise

# load model
model = joblib.load("severity_model.pkl")
print("Model loaded.")

ref = db.reference("/AccidentEvents")  # monitor accident events; change if needed

def process_and_update(key, data):
    try:
        A = float(data.get("Acceleration", 0))
        Gx = float(data.get("Gx", 0))
        Gy = float(data.get("Gy", 0))
        Gz = float(data.get("Gz", 0))
        X = np.array([[A, Gx, Gy, Gz]])
        pred = model.predict(X)[0]
        severity_label = int(pred)  # 0 or 1
        # write back under same node
        db.reference(f"/AccidentEvents/{key}/Severity").set(int(severity_label))
        print(f"Updated {key} → Severity: {severity_label}")
    except Exception as e:
        print("Process error:", e)

# callback style not directly provided by admin SDK: use polling listener
print("Starting polling listener (every 3s)...")
seen = set()
while True:
    data = ref.get()
    if data and isinstance(data, dict):
        for k, v in data.items():
            if k in seen:
                continue
            if isinstance(v, dict):
                # skip if Severity already exists
                if 'Severity' in v:
                    seen.add(k)
                    continue
                process_and_update(k, v)
                seen.add(k)
    time.sleep(3)
