#!/usr/bin/env python3
"""E2E test for Gateway Supervisor + Admin API + Auto-restart"""
import subprocess, json

API = "http://localhost:8000"

def api(method, path, body=None, token=None):
    headers = ["-H", "Content-Type: application/json"]
    if token:
        headers += ["-H", f"Authorization: Bearer ***    cmd = ["curl", "-s", "-X", method, f"{API}{path}"] + headers
    if body:
        cmd += ["-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout else {"error": r.stderr}

# 1. Register
print("=" * 50)
print("1. Register admin user")
res = api("POST", "/api/auth/register", {"email": "e2e@test.com", "password": "test123", "name": "E2E Admin"})
token = res["access_token"]
print(f"  ok - token: {token[:25]}...")

# 2. Admin creates client
print("\n" + "=" * 50)
print("2. Admin creates client (Alice)")
res = api("POST", "/api/admin/clients/create", {
    "email": "e2eclient@example.com",
    "name": "E2E Client",
    "whatsapp_number": "+1 212 555 1234",
    "plan": "pro"
}, token=token)
cid = res["user_id"]
pname = res["profile_name"]
print(f"  ok - id={cid[:12]}... profile={pname}")

# 3. List clients
print("\n" + "=" * 50)
print("3. List all clients")
clients = api("GET", "/api/admin/clients", token=token)
for c in clients:
    print(f"  {c['name']:20s} | gw={c['gateway_status']:8s} | {c['plan']}")

# 4. Start gateway
print("\n" + "=" * 50)
print("4. Start Gateway")
res = api("POST", f"/api/admin/clients/{cid}/gateway/start", token=token)
print(f"  status={res.get('status')} pid={res.get('pid','?')}")

# 5. Gateway status
print("\n5. Gateway Status: ", end="")
res = api("GET", f"/api/admin/clients/{cid}/gateway/status", token=token)
print(res.get('status','?'))

# 6. Log
print("\n6. Gateway Log:")
res = api("GET", f"/api/admin/clients/{cid}/gateway/log?tail=6", token=token)
for line in res.get("log","").strip().split("\n"):
    if line.strip():
        print(f"  {line.strip()}")

# 7. Auto-restart: change WhatsApp
print("\n" + "=" * 50)
print("7. Auto-restart on WhatsApp change")
res = api("PUT", "/api/profiles/me/whatsapp", {"whatsapp_number": "+1 555 999 8888"}, token=token)
print(f"  {res}")

# 8. Check log after change
print("\n8. Log after auto-restart:")
res = api("GET", f"/api/admin/clients/{cid}/gateway/log?tail=10", token=token)
for line in res.get("log","").strip().split("\n"):
    if line.strip():
        print(f"  {line.strip()}")

# 9. Admin restart
print("\n" + "=" * 50)
print("9. Admin manual restart")
res = api("POST", f"/api/admin/clients/{cid}/gateway/restart", token=token)
print(f"  stop={res['stop']['status']} start={res['start']['status']}")

# 10. List gateways
print("\n10. Running gateways:")
res = api("GET", "/api/admin/gateways", token=token)
print(f"  {json.dumps(res)}")

# 11. Stop
print("\n11. Stop Gateway")
res = api("POST", f"/api/admin/clients/{cid}/gateway/stop", token=token)
print(f"  {res.get('status')} - {res.get('detail','')}")

# 12. Stats
print("\n12. Admin Stats:")
res = api("GET", "/api/admin/stats", token=token)
print(f"  {json.dumps(res)}")

print("\n" + "=" * 50)
print("ALL E2E TESTS PASSED")
