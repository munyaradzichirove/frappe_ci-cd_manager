import frappe
import json

@frappe.whitelist(allow_guest=True)
def github_webhook():
    # Raw request data
    raw_data = frappe.request.data

    try:
        payload = json.loads(raw_data)
    except Exception:
        payload = raw_data

    # Print EVERYTHING (terminal + bench logs)
    print("\n" + "=" * 80)
    print("🔥 GITHUB WEBHOOK RECEIVED 🔥")
    print("=" * 80)

    print("\n👉 HEADERS:")
    for k, v in frappe.request.headers.items():
        print(f"{k}: {v}")

    print("\n👉 PAYLOAD:")
    print(json.dumps(payload, indent=4))

    print("\n" + "=" * 80)

    return {
        "status": "ok",
        "message": "Webhook received and logged"
    }
