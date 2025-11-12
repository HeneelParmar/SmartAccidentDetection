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
service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})

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
