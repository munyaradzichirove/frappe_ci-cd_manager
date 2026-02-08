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

    app_name = "Payroll"  # existing App Manager doc

    # get the existing App Manager doc
    doc = frappe.get_doc("App Manager", app_name)

    for commit in commits:
        committer = commit.get("committer", {}).get("name")
        commit_id = commit.get("id")
        message = commit.get("message")
        received_time = now_datetime().astimezone(tz)

        # append to child table
        doc.append("commit_history", {
            "user": committer,
            "commit_sha": commit_id,
            "commit_message": message,
            "received_time": received_time
        })

    # only save the doc (updates child table)
    doc.save(ignore_permissions=True)

    return {"status": "success", "commits_added": len(commits)}
