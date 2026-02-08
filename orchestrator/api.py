import frappe
import json
from urllib.parse import parse_qs

@frappe.whitelist(allow_guest=True)
def github_webhook():
    raw_data = frappe.request.data  # bytes
    raw_text = raw_data.decode("utf-8")  # decode bytes to str

    # GitHub sent application/x-www-form-urlencoded
    # It comes as: payload=%7B....%7D
    # We need to parse it
    parsed = parse_qs(raw_text)
    payload_str = parsed.get("payload", [None])[0]

    try:
        payload = json.loads(payload_str) if payload_str else raw_text
    except Exception:
        payload = raw_text

    # Print everything
    print("\n" + "=" * 80)
    print("🔥 GITHUB WEBHOOK RECEIVED 🔥")
    print("=" * 80)

    print("\n👉 HEADERS:")
    for k, v in frappe.request.headers.items():
        print(f"{k}: {v}")

    print("\n👉 PAYLOAD:")
    print(json.dumps(payload, indent=4))

    print("\n" + "=" * 80)
    return {"status": "ok", "message": "Webhook received and logged"}
 