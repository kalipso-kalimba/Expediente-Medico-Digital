"""Debug login flow"""
import requests, re

s = requests.Session()
BASE = "http://127.0.0.1:8765"

# Clear cookies and login
s.cookies.clear()
r = s.get(f"{BASE}/")
print(f"GET / status={r.status_code}")
print(f"Cookies after GET: {dict(s.cookies)}")

csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
r = s.post(f"{BASE}/login",
    data={"username": "doctor", "password": "test123", "csrf_token": csrf},
    allow_redirects=False)
print(f"POST /login status={r.status_code}")
print(f"Location: {r.headers.get('Location', '')}")
print(f"Set-Cookie: {r.headers.get('Set-Cookie', 'NONE')}")
print(f"Cookies after login: {dict(s.cookies)}")

# Try to access doctor page
r = s.get(f"{BASE}/doctor")
print(f"GET /doctor status={r.status_code}")
print(f"Cookies: {dict(s.cookies)}")
print(f"'Panel principal' in text: {'Panel principal' in r.text}")
print(f"Response length: {len(r.text)}")
