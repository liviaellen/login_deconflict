import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
from sklearn.ensemble import IsolationForest
import logging
import uvicorn

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- IN-MEMORY DATA STORE (Simulated DB) ---
users_db = {
    "alice": {"password": "password123", "history": []},
    "bob":   {"password": "securepass",   "history": []},
    "charlie": {"password": "password123", "history": []}
}

# --- RISK ENGINE ---
class RiskEngine:
    def __init__(self):
        # Unsupervised model for anomaly detection
        self.ml_model = IsolationForest(contamination=0.1, random_state=42)

        # Training data: hours usually between 8 AM and 6 PM
        X_train = []
        for h in range(8, 19):
            X_train.append([h, 1])
        X_train = np.array(X_train * 5)
        self.ml_model.fit(X_train)

    def calculate_risk(self, username: str, context: dict):
        score = 0
        reasons = []
        user_history = users_db.get(username, {}).get("history", [])

        # 1. RULE: Velocity Check
        recent_logins = [
            log for log in user_history
            if (datetime.datetime.now() - log['timestamp']).total_seconds() < 300
        ]
        if len(recent_logins) >= 5:
            score += 40
            reasons.append("High Login Velocity")

        # 2. RULE: New Device Check
        known_devices = {log.get('device_id') for log in user_history}
        if context.get('device_id') not in known_devices and user_history:
            score += 30
            reasons.append("New Device")

        # 3. RULE: IP Reputation
        if context.get('ip') == '1.2.3.4':
            score += 80
            reasons.append("Bad IP Reputation")

        # 4. ML: Anomaly Detection
        current_hour = context.get('hour', datetime.datetime.now().hour)
        features = np.array([[current_hour, 1]])
        prediction = self.ml_model.predict(features)

        print(f"ML Prediction for hour {current_hour}: {prediction[0]}")

        if prediction[0] == -1:
            score += 35
            reasons.append("ML: Anomalous Login Time")

        return min(score, 100), reasons

risk_engine = RiskEngine()

# --- AUTH ROUTES ---

@app.post("/login")
async def login(request: Request):
    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    context = data.get('context', {})

    user = users_db.get(username)
    if not user or user['password'] != password:
        raise HTTPException(status_code=401, detail={"status": "deny", "reason": "Invalid credentials"})

    risk_score, reasons = risk_engine.calculate_risk(username, context)

    decision = "allow"
    if risk_score > 70:
        decision = "block"
    elif risk_score > 20:
        decision = "challenge"

    log_entry = {
        "timestamp": datetime.datetime.now(),
        "ip": context.get('ip'),
        "device_id": context.get('device_id'),
        "risk_score": risk_score,
        "decision": decision
    }
    user['history'].append(log_entry)

    response = {
        "status": decision,
        "risk_score": risk_score,
        "reasons": reasons
    }

    if decision == "challenge":
        response["message"] = "MFA Required"
    elif decision == "block":
        response["message"] = "Account Locked due to suspicious activity"

    return response

@app.post("/verify-challenge")
async def verify_challenge(request: Request):
    data = await request.json()
    code = data.get('code')

    if code == "123456":
        return {"status": "allow", "message": "MFA Verified"}
    raise HTTPException(status_code=401, detail={"status": "deny", "message": "Invalid MFA Code"})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
