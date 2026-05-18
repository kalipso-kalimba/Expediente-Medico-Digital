"""Debug create_encounter flow"""
import requests, re, time

s = requests.Session()
BASE = "http://127.0.0.1:8765"

# Login
r = s.get(f"{BASE}/")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
print(f"Login page CSRF: {csrf[:20]}...")
r = s.post(f"{BASE}/login",
    data={"username": "doctor", "password": "test123", "csrf_token": csrf},
    allow_redirects=False)
print(f"Login response: {r.status_code}, cookies: {dict(s.cookies)}")

# Check doctor page
r = s.get(f"{BASE}/doctor")
print(f"Doctor page: {r.status_code}")
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
if m:
    print(f"Doctor CSRF: {m.group(1)[:20]}...")
else:
    print("NO CSRF on doctor page!")
    print(f"Has 'Panel principal': {'Panel principal' in r.text}")
    print(f"Redirected? Location in history: {r.history}")

# Create link
csrf = m.group(1)
r = s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)
print(f"Create link: {r.status_code}, Location: {r.headers.get('Location','')}")

# Get token
r = s.get(f"{BASE}/doctor")
tokens = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
print(f"Tokens found: {len(tokens)}, last: {tokens[-1] if tokens else 'NONE'}")
tok = tokens[-1]

# Load patient form
r = s.get(f"{BASE}/patient/{tok}")
print(f"Patient form: {r.status_code}")
m2 = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
if m2:
    print(f"Patient CSRF: {m2.group(1)[:20]}...")
else:
    print("NO CSRF on patient form!")
    print(f"Response preview: {r.text[:300]}")
