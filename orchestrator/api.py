import frappe
from frappe.utils import now_datetime
from pytz import timezone

@frappe.whitelist(allow_guest=True)
def github_webhook(**kwargs):
    import json

    # Frappe receives the payload as a string sometimes
    payload = kwargs.get("payload")
    if isinstance(payload, str):
        payload = json.loads(payload)

    commits = payload.get("commits", [])
    tz = timezone("Africa/Harare")

    app_name = "Payroll"  # Replace with your App Manager name or find dynamically

    for commit in commits:
        committer = commit.get("committer", {}).get("name")
        commit_id = commit.get("id")
        message = commit.get("message")
        received_time = now_datetime().astimezone(tz)

        # Insert into child table
        frappe.get_doc({
            "doctype": "App Manager",
            "app_name": app_name,
            "commit_history": [{
                "user": committer,
                "commit_sha": commit_id,
                "commit_message": message,
                "received_time": received_time
            }]
        }).insert(ignore_permissions=True)
    
    return {"status": "success", "commits_processed": len(commits)}
