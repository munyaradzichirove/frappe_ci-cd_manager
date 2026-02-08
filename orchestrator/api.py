import frappe
from frappe.utils import now_datetime
from pytz import timezone

@frappe.whitelist(allow_guest=True)
def github_webhook(**kwargs):
    import json
    payload = kwargs.get("payload")
    if isinstance(payload, str):
        payload = json.loads(payload)

    commits = payload.get("commits", [])
    tz = timezone("Africa/Harare")

    app_name = "Payroll"

    # get parent using filter
    doc = frappe.get_all("App Manager", filters={"app_name": app_name}, limit=1)
    if not doc:
        # parent doesn't exist, create it
        doc = frappe.get_doc({
            "doctype": "App Manager",
            "app_name": app_name
        }).insert(ignore_permissions=True)
    else:
        # fetch the full doc by its actual name
        doc = frappe.get_doc("App Manager", doc[0].name)

    for commit in commits:
        committer = commit.get("committer", {}).get("name")
        commit_id = commit.get("id")
        message = commit.get("message")
        received_time = now_datetime().astimezone(tz)

        doc.append("commit_history", {
            "user": committer,
            "commit_sha": commit_id,
            "commit_message": message,
            "received_time": received_time
        })

    doc.save(ignore_permissions=True)

    return {"status": "success", "commits_added": len(commits)}
