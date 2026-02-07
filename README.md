# Flowmaster Orchestrator

**Flowmaster** is the CI/CD master site. **Orchestrator** is the Frappe app inside it that manages deployments to remote Frappe sites.

---

## **Features**

* Centralized GitHub webhook receiver
* Manage multiple apps/repos in one place
* Per-site deployment settings (pause, pull now, branch override)
* Commit history logging (commit SHA, message, time received)
* Deployment logging (status, last deployment time)
* Optional scheduling and timezone support
* Fully powered by Ansible for remote deployments

---

## **How It Works**

1. GitHub webhook sends a push event to Flowmaster.
2. Orchestrator checks which app the commit belongs to.
3. Loops through the sites linked under that app.
4. Executes Ansible playbooks to pull, migrate, and restart remote sites.
5. Logs commit messages, deployment status, and timestamps.

---

## **DocTypes Overview**

* **App**: Parent DocType storing repo info and linking child site deployments.
* **Site Deployment**: Child table under App; stores per-site configs and controls.
* **Site**: Reference table for all available sites (name + IP).
* **Deployment Log**: Tracks status and time of each deployment.
* **Commit History**: Tracks commit SHA, message, and time received from GitHub.

---

## **Getting Started**

1. Install Frappe and setup the Flowmaster site.
2. Install the **Orchestrator** app.
3. Add your apps/repos in Orchestrator.
4. Add sites to each app in the child table.
5. Set up GitHub webhooks pointing to Flowmaster.
6. Configure Ansible inventory and playbooks for remote deployments.

---

## **Future Enhancements**

* Rollback specific commits
* Advanced scheduling of deployments
* Visual commit & deployment dashboards

