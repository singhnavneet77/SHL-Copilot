import requests
import json

url = "http://localhost:8000/chat"
headers = {"Content-Type": "application/json"}

# Turn 1: Vague query (should clarify)
payload = {
    "messages": [
        {"role": "user", "content": "I need to hire an IT professional"}
    ]
}

print("Testing Turn 1 (Vague query):")
r = requests.post(url, json=payload, headers=headers)
print(f"Status: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2)}")
print("-" * 60)

# Turn 2: Specific request
payload_specific = {
    "messages": [
        {"role": "user", "content": "I need a Java developer with stakeholder management experience."}
    ]
}

print("Testing Turn 2 (Specific query):")
r_spec = requests.post(url, json=payload_specific, headers=headers)
print(f"Status: {r_spec.status_code}")
print(f"Response: {json.dumps(r_spec.json(), indent=2)}")
print("-" * 60)
