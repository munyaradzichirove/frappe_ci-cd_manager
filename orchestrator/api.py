import frappe
from frappe.utils import now_datetime
from pytz import timezone
import requests
import subprocess
import os

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
    run_ansible_playbook(repo_url)
    return {"status": "success", "commits_added": len(commits)}

def send_telegram_message(committer, commit_id, message, received_time):
    """
    Sends a commit notification to Telegram using bot token and chat ID from  Orchestrator Settings.
    """
    # Get the Orchestrator Settings record (assuming single doctype or only one record)
    settings = frappe.get_single("Orchestrator Settings")

    BOT_TOKEN = settings.telegram_bot_token
    CHAT_ID = settings.chat_id
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
    print("📤 Sending Telegram message...")
    print("URL:", url)
    print("Payload:", payload)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print("⏳ Response received, status code:", resp.status_code)
        resp.raise_for_status()
        print("✅ Telegram message sent successfully!")
        print("Response JSON:", resp.json())
        return {"status": "success", "response": resp.json()}
    except Exception as e:
        print("❌ Failed to send Telegram message: ", str(e))
        return {"status": "error", "error": str(e)}

@frappe.whitelist()
def test_telegram(telegram_bot_token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "Test message from Orchestrator Settings!"
        }
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            return "Telegram message sent successfully!"
        else:
            return f"Failed to send message: {r.text}"
    except Exception as e:
        return f"Error: {str(e)}"

def enqueue_ansible_playbook():
    frappe.enqueue(
        "orchestrator.api.run_ansible_playbook",
        queue="short",
        timeout=3600  # 1 hour max
)
def run_ansible_playbook(repo_url):
    """
    Runs Ansible playbook for the given repo and streams output to last_deploy_log.
    """
    import subprocess, os, frappe
    from rq.registry import StartedJobRegistry
    from frappe.utils.background_jobs import get_queues

    base_path = os.path.dirname(os.path.abspath(__file__))
    ansible_path = os.path.join(base_path, "ansible")
    inventory_file = os.path.join(ansible_path, "inventory.ini")
    playbook_file = os.path.join(ansible_path, "deploy.yml")
    build_inventory_from_repo(repo_url)

    # fetch the App Manager doc
    docs = frappe.get_all("App Manager", filters={"repo": repo_url}, limit=1)
    if not docs:
        frappe.throw(f"No App Manager found for repo {repo_url}")
    doc = frappe.get_doc("App Manager", docs[0].name)

    # reset log
    doc.last_deploy_log = ""
    doc.save(ignore_permissions=True)
    def append_log(line):
        doc.last_deploy_log = (doc.last_deploy_log or "") + line + "\n"
        doc.save(ignore_permissions=True)

    try:
        process = subprocess.Popen(
            ["ansible-playbook", "-i", inventory_file, playbook_file],
            cwd=ansible_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        # stream output line by line to doc
        for line in process.stdout:
            line = line.rstrip()
            print(line) 
            append_log(line)

        process.wait()
        append_log("\n✅ Deployment is finished!\n")
        return {"status": "success"}

    except Exception as e:
        append_log(f"\n❌ Deployment failed: {str(e)}\n")
        return {"status": "error", "error": str(e)}

def build_inventory_from_repo(repo_url):
    import os, frappe

    docs = frappe.get_all("App Manager", filters={"repo": repo_url}, limit=1)
    if not docs:
        frappe.throw(f"No App Manager found for repo {repo_url}")

    doc = frappe.get_doc("App Manager", docs[0].name)

    lines = ["[erp_servers]"]
    seen_hosts = set()

    for row in doc.sites:
        if row.pause_pull:
            continue

        host = (row.ip or "").strip()
        if not host:
            continue

        if host in seen_hosts:
            continue
        seen_hosts.add(host)

        real_site = frappe.db.get_value(
            "Site Inventory",
            row.site,
            "site_name"
        )

        if not real_site:
            frappe.throw(f"Site Inventory {row.site} has no site_name")

        safe_site = real_site.replace('"', '\\"')

        lines.append(
            f'{host} '
            f'ansible_user=frappe '
            f'ansible_ssh_private_key_file=~/.ssh/id_rsa '
            f'site_name="{safe_site}"'
        )

    if len(lines) == 1:
        frappe.throw("No active sites to deploy (all paused)")

    base_path = os.path.dirname(os.path.abspath(__file__))
    inventory_path = os.path.join(base_path, "ansible", "inventory.ini")

    with open(inventory_path, "w") as f:
        f.write("\n".join(lines))

    return inventory_path
