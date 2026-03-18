"""
Quick smoke-test for the deployed Railway backend API.
Uses only Python stdlib (urllib) -- no pip install needed.
"""

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://ind-money-review-analyser-production.up.railway.app"

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"
SKIP = "\033[93m SKIP \033[0m"

results = []


def test(name, method, path, json_body=None, timeout=300):
    url = f"{BASE}{path}"
    print(f"\n{'='*60}")
    print(f"  Testing: {name}")
    print(f"  {method.upper()} {url}")
    if json_body:
        print(f"  Body: {json_body}")
    print(f"{'='*60}")

    try:
        start = time.time()
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, method="POST",
                headers={"Content-Type": "application/json"},
            )
        else:
            req = urllib.request.Request(url, method=method.upper())

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.time() - start
            status = resp.status
            body_bytes = resp.read()

        status_ok = 200 <= status < 300
        tag = PASS if status_ok else FAIL
        print(f"  Status : {status} {tag}  ({elapsed:.1f}s)")

        try:
            body = json.loads(body_bytes)
            for key, val in body.items():
                val_str = str(val)
                if len(val_str) > 120:
                    val_str = val_str[:120] + "…"
                print(f"    {key}: {val_str}")
        except (json.JSONDecodeError, AttributeError):
            text = body_bytes.decode("utf-8", errors="replace")[:200]
            print(f"  Body (text): {text}{'…' if len(body_bytes) > 200 else ''}")

        results.append((name, status_ok, f"{status} in {elapsed:.1f}s"))
        return status_ok

    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        print(f"  {FAIL} HTTP {e.code}  ({elapsed:.1f}s)")
        try:
            err_body = json.loads(e.read())
            print(f"    detail: {err_body.get('detail', str(err_body))[:200]}")
        except Exception:
            pass
        results.append((name, False, f"HTTP {e.code} in {elapsed:.1f}s"))
        return False

    except urllib.error.URLError as e:
        print(f"  {FAIL} Connection error: {e.reason}")
        results.append((name, False, f"connection error: {e.reason}"))
        return False

    except TimeoutError:
        print(f"  {FAIL} Timed out after {timeout}s")
        results.append((name, False, "timeout"))
        return False


print("\n" + "#" * 60)
print("  IND Money Review Analyser -- API Smoke Test")
print(f"  Target: {BASE}")
print("#" * 60)

# 1. Health check
test("Health Check", "get", "/api/health")

# 2. State (should be empty initially)
test("State (initial)", "get", "/api/state")

# 3. Scrape
ok = test("Phase 1: Scrape", "post", "/api/scrape", {"weeks": 8})

# 4. Scrub
if ok:
    ok = test("Phase 2: Scrub PII", "post", "/api/scrub", {})
else:
    print(f"\n{SKIP} Skipping Phase 2 (scrape failed)")
    results.append(("Phase 2: Scrub PII", False, "skipped"))

# 5. Analyze
if ok:
    ok = test("Phase 3: Analyze (Gemini)", "post", "/api/analyze", {})
else:
    print(f"\n{SKIP} Skipping Phase 3 (scrub failed)")
    results.append(("Phase 3: Analyze (Gemini)", False, "skipped"))

# 6. Report
if ok:
    ok = test("Phase 4: Generate Report", "post", "/api/report", {"recipient_name": "Test User"})
else:
    print(f"\n{SKIP} Skipping Phase 4 (analyze failed)")
    results.append(("Phase 4: Generate Report", False, "skipped"))

# 7. Report preview
if ok:
    test("Report Preview (HTML)", "get", "/api/report/preview")

# 8. Final state
test("State (final)", "get", "/api/state")

# ── Summary ──────────────────────────────────────────────────
print("\n\n" + "#" * 60)
print("  SUMMARY")
print("#" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    tag = PASS if ok else FAIL
    print(f"  {tag}  {name:35s}  {detail}")
print(f"\n  {passed}/{total} passed")
print("#" * 60 + "\n")

sys.exit(0 if passed == total else 1)
