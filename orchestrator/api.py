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
    frappe.db.commit() 
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
def send_telegram_message_success(message):
    settings = frappe.get_single("Orchestrator Settings")

    BOT_TOKEN = settings.telegram_bot_token
    CHAT_ID = settings.chat_id

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    r = requests.post(url, json=payload, timeout=10)
    return r.status_code == 200

def run_ansible_playbook(repo_url):
    import subprocess, os
    from frappe.utils import now_datetime

    base_path = os.path.dirname(os.path.abspath(__file__))
    ansible_path = os.path.join(base_path, "ansible")
    inventory_file = os.path.join(ansible_path, "inventory.ini")
    playbook_file = os.path.join(ansible_path, "deploy.yml")

    build_inventory_from_repo(repo_url)

    docs = frappe.get_all("App Manager", filters={"repo": repo_url}, limit=1)
    if not docs:
        frappe.throw(f"No App Manager found for repo {repo_url}")
    doc = frappe.get_doc("App Manager", docs[0].name)

    # reset log
    doc.last_deploy_log = ""
    doc.save(ignore_permissions=True)

    deployed_sites = []
    error_count = 0

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

        for line in process.stdout:
            line = line.rstrip()
            append_log(line)

        process.wait()

        # --- update sites ---
        for site_row in doc.sites:
            site_row.last_deployment_status = "Success"
            site_row.last_deployment_time = now_datetime()
            deployed_sites.append(site_row.site)
        
        doc.save(ignore_permissions=True)
        message = (
            "✅ Deployment completed\n\n"
            f"Repo: {repo_url}\n"
            f"Sites: {', '.join(deployed_sites)}\n"
            f"Errors: {error_count}"
        )
        send_telegram_message_success(message)

        return {"status": "success"}

    except Exception as e:
        error_count += 1
        append_log(f"\n❌ Deployment failed: {str(e)}\n")

        telegram_bot_token, chat_id = get_telegram_config()
        send_telegram_message(
            telegram_bot_token,
            chat_id,
            f"❌ Deployment failed\nRepo: {repo_url}\nError: {str(e)}"
        )


        return {"status": "error", "error": str(e)}
def build_inventory_from_repo(repo_url):
    import os, frappe
    # Fetch the App Manager doc
    docs = frappe.get_all("App Manager", filters={"repo": repo_url}, limit=1)
    if not docs:
        frappe.throw(f"No App Manager found for repo {repo_url}")

    doc = frappe.get_doc("App Manager", docs[0].name)

    lines = ["[erp_servers]"]
    seen_entries = set()
    for row in doc.sites:
        if row.pause_pull:
            continue

        host_ip = (row.ip or "").strip()
        if not host_ip:
            continue


        site_name = frappe.db.get_value("Site Inventory", row.site, "site_name")
        if not site_name:
            frappe.throw(f"Site Inventory {row.site} has no site_name")

        safe_site = site_name.replace('"', '\\"')

        # Create a unique logical host identifier: site_name + IP
        identifier = f"{safe_site.replace(' ', '_')}_{host_ip.replace('.', '_')}"

        # Skip duplicates
        key = (identifier, host_ip)
        if key in seen_entries:
            continue
        seen_entries.add(key)

        # Append inventory line with ansible_host
        lines.append(
            f'{identifier} ansible_host={host_ip} '
            f'ansible_user=frappe '
            f'ansible_ssh_private_key_file=~/.ssh/id_rsa '
            f'site_name="{safe_site}"'
        )

    if len(lines) == 1:
        frappe.throw("No active sites to deploy (all paused)")

    # Write inventory file
    base_path = os.path.dirname(os.path.abspath(__file__))
    inventory_path = os.path.join(base_path, "ansible", "inventory.ini")

    with open(inventory_path, "w") as f:
        f.write("\n".join(lines))
    return inventory_path
