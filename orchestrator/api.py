import frappe
from frappe.utils import now_datetime
from pytz import timezone
import requests

@frappe.whitelist(allow_guest=True)
def github_webhook(**kwargs):
    import json
    payload = kwargs.get("payload")
    if isinstance(payload, str):
        payload = json.loads(payload)

    commits = payload.get("commits", [])
    tz = timezone("Africa/Harare")

    repo_url = payload.get("repository", {}).get("html_url")
    if not repo_url:
        frappe.throw("No repository URL found in payload")

    # get parent using repo filter
    doc_list = frappe.get_all("App Manager", filters={"repo": repo_url}, limit=1)
    if doc_list:
        doc = frappe.get_doc("App Manager", doc_list[0].name)
    else:
        # create parent if it doesn't exist
        doc = frappe.get_doc({
            "doctype": "App Manager",
            "repo": repo_url
        }).insert(ignore_permissions=True)

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
    send_telegram_message(committer, commit_id, message, received_time)
    return {"status": "success", "commits_added": len(commits)}

def send_telegram_message(committer, commit_id, message, received_time):
    """
    Sends a commit notification to Telegram.
    """
    BOT_TOKEN = "8351272834:AAFZPJmdoCyjH_Ia- SUAUdmTL1D5Ecrzr4A"
    CHAT_ID = "YOUR_CHAT_ID"

    text = (
        f"🛠️ *New Commit Received!*\n\n"
        f"*Committer:* {committer}\n"
        f"*Commit SHA:* `{commit_id}`\n"
        f"*Message:* {message}\n"
        f"*Received Time:* {received_time}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"status": "success", "response": resp.json()}
    except Exception as e:
        return {"status": "error", "error": str(e)}
