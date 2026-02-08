import frappe

@frappe.whitelist(allow_guest=True)
def github_webhook():
    payload = frappe.local.form_dict  # raw POST data
    
    import json
    try:
        # GitHub sends x-www-form-urlencoded if that's your content type
        payload = json.loads(payload.get("payload"))
    except:
        pass  # already a dict

    for commit in payload.get("commits", []):
        committer = commit["committer"]["name"]
        timestamp = commit["timestamp"]
        message = commit["message"]
        commit_id = commit["id"]

        print(f"📌 Commit by {committer} at {timestamp}")
        print(f"💬 Message: {message}")
        print(f"🔗 Commit ID: {commit_id}")
        print("-" * 40)

    return "OK"
