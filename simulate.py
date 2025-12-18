import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_scenario(name, username, password, context, expected_status):
    print(f"\n--- Scenario: {name} ---")
    payload = {
        "username": username,
        "password": password,
        "context": context
    }

    try:
        response = requests.post(f"{BASE_URL}/login", json=payload)
        data = response.json()

        print(f"Request Context: {context}")
        print(f"Response: {data}")

        if data.get("status") == expected_status:
            print("RESULT: PASS ✅")
        else:
            print(f"RESULT: FAIL ❌ (Expected {expected_status}, got {data.get('status')})")

        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    # Wait for server to start
    time.sleep(2)

    # 1. Happy Path
    # Known device, good IP, normal hour (9 AM)
    # Note: In the mock DB, history is empty first, so first login might be a bit risky (New Device)
    # Let's do one login to establish history, then a second one that should be purely happy.
    print("Initializing user history...")
    requests.post(f"{BASE_URL}/login", json={
        "username": "alice", "password": "password123",
        "context": {"device_id": "device_A", "ip": "192.168.1.1", "hour": 9}
    })

    test_scenario(
        "Happy Path (Known Device, Normal Time)",
        "alice", "password123",
        {"device_id": "device_A", "ip": "192.168.1.1", "hour": 10},
        "allow"
    )

    # 2. New Device (Medium Risk)
    test_scenario(
        "New Device (Should Challenge)",
        "alice", "password123",
        {"device_id": "device_B_NEW", "ip": "192.168.1.1", "hour": 11},
        "challenge"
    )

    # 3. Bad IP (High Risk -> Block)
    test_scenario(
        "Bad IP (Should Block)",
        "alice", "password123",
        {"device_id": "device_A", "ip": "1.2.3.4", "hour": 12},
        "block"
    )

    # 4. ML Anomaly (Unusual Time - 3 AM)
    # Our simple ML model was trained on 9-16 hours. 3 AM is an outlier.
    test_scenario(
        "Anomaly: 3 AM Login (Should Challenge/Block depending on score)",
        "alice", "password123",
        {"device_id": "device_A", "ip": "192.168.1.1", "hour": 3},
        "challenge" # Prediction: ML adds 35 points. 35 > 20 (challenge threshold).
    )

    # 5. Velocity Check
    print("\n--- Testing Velocity ---")
    requests.post(f"{BASE_URL}/login", json={
        "username": "charlie", "password": "password123",
        "context": {"device_id": "device_C", "ip": "3.3.3.3", "hour": 9}
    })

    for i in range(7):
        # Initial login (1) + 4 attempts (2,3,4,5) = 5 total.
        # The 6th attempt (i=4, Attempt #5) will see 5 historical logins and trigger the rule.
        expected = "allow" if i < 4 else "challenge"
        # Note: If it hits risk threshold 40, it challenges. If it hits >70 it blocks.
        test_scenario(
            f"Velocity Attempt #{i+1}",
            "charlie", "password123",
            {"device_id": "device_C", "ip": "3.3.3.3", "hour": 14},
            expected
        )

if __name__ == "__main__":
    main()
