import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint, today

from lms.lms.custom.resource_constants import (
	RESOURCE_ROOT_FOLDER,
	is_effectively_published,
	is_under_resource_root,
)


def notify_resource_change(doc, method):
	"""Single dispatcher for all Resources notifications - registered on
	File.after_insert and File.on_update, and called explicitly (with
	method="replace") from resource_api.replace_resource_file().

	Deliberately just two message types, both scoped to the folder, not
	the individual file:
	- "Folder X was published": fires once, exactly when a folder's own
	  `published` flag flips 0 -> 1 while it's genuinely visible (every
	  ancestor above it is already published too).
	- "Folder X was updated": fires when a file becomes visible inside an
	  already-published folder - a newly published file (upload, or a
	  later publish-toggle) or a replace of existing content.

	Delete is deliberately never notified. Anything not yet effectively
	published never notifies either - notification timing is driven
	entirely by visibility, not raw file activity, so admins can draft
	freely without spamming anyone.
	"""
	if doc.is_folder:
		_maybe_notify_folder_published(doc)
	else:
		_maybe_notify_folder_updated(doc, method)


def _maybe_notify_folder_published(folder_doc):
	if folder_doc.name == RESOURCE_ROOT_FOLDER:
		return  # bootstrap/technical root, not a meaningful admin action
	if not is_under_resource_root(folder_doc.name):
		return
	if folder_doc.notification_sent:
		return
	if not folder_doc.has_value_changed("published") or not folder_doc.published:
		return
	if not is_effectively_published(folder_doc.name):
		return  # an ancestor is still a draft, or publish_on hasn't arrived yet

	_dispatch("published", folder_doc)
	frappe.db.set_value("File", folder_doc.name, "notification_sent", 1)


def _maybe_notify_folder_updated(file_doc, method):
	if not is_under_resource_root(file_doc.folder):
		return
	if file_doc.notification_sent:
		return

	is_replace = method == "replace"
	if not is_replace and method != "after_insert" and not file_doc.has_value_changed("published"):
		return  # unrelated save (rename, move, etc.) - nothing to announce

	if not is_effectively_published(file_doc.name):
		return  # file itself, or its folder chain, is still a draft or not-yet-scheduled

	folder_doc = frappe.get_doc("File", file_doc.folder)
	_dispatch("updated", folder_doc)
	frappe.db.set_value("File", file_doc.name, "notification_sent", 1)


def send_scheduled_publish_notifications():
	"""Daily scheduled task - catches resources whose `publish_on` date
	has now arrived. Necessary because the doc_event-driven paths above
	only fire on an actual document save; nothing saves a File just
	because a date on the calendar was reached, same reason
	LMS Course's own published_on/notification_sent pair needs its own
	daily job (send_notification_for_published_courses) rather than
	relying on doc_events alone.

	Folders are processed before files, deliberately: if a file's own
	`publish_on` already passed (it was just waiting on its folder) and
	the *folder's* `publish_on` also arrives today, both would otherwise
	independently pass their checks in the same run - one real event
	("this folder just went live") would send two notifications ("Folder
	X was published" AND "Folder X was updated") for what the audience
	experiences as a single reveal. Same "only the outermost trigger
	fires, no cascading" principle already applied to the immediate
	doc_event path - the scheduled path needs the same guarantee applied
	explicitly, since it evaluates every pending candidate independently
	rather than reacting to one specific save.
	"""
	candidates = frappe.get_all(
		"File",
		filters={
			"published": 1,
			"publish_on": ["<=", today()],
			"notification_sent": 0,
		},
		fields=["name", "is_folder", "folder"],
	)

	folders_freshly_published = set()

	for row in candidates:
		if not row.is_folder:
			continue
		if row.name == RESOURCE_ROOT_FOLDER:
			continue
		if not is_under_resource_root(row.name):
			continue
		if not is_effectively_published(row.name):
			continue  # an ancestor is still a draft or itself not-yet-scheduled

		folder_doc = frappe.get_doc("File", row.name)
		_dispatch("published", folder_doc)
		frappe.db.set_value("File", row.name, "notification_sent", 1)
		folders_freshly_published.add(row.name)

	for row in candidates:
		if row.is_folder:
			continue
		if not is_under_resource_root(row.folder):
			continue
		if not is_effectively_published(row.name):
			continue  # an ancestor is still a draft or itself not-yet-scheduled

		if _has_freshly_published_ancestor(row.folder, folders_freshly_published):
			# Already covered by that folder's own "published" message
			# above - mark as handled without a second notification.
			frappe.db.set_value("File", row.name, "notification_sent", 1)
			continue

		folder_doc = frappe.get_doc("File", row.folder)
		_dispatch("updated", folder_doc)
		frappe.db.set_value("File", row.name, "notification_sent", 1)


def _has_freshly_published_ancestor(folder, freshly_published_set):
	current = folder
	while current:
		if current in freshly_published_set:
			return True
		if current == RESOURCE_ROOT_FOLDER:
			break
		current = frappe.db.get_value("File", current, "folder")
	return False


def get_lms_notification_recipients():
	"""Enabled users who actually have LMS/Resources access - not every
	enabled account on the site, most of which (HR-only, finance-only,
	integration accounts, etc.) have nothing to do with the LMS. Mirrors
	the same "is this an LMS role" rule dashboard_api.py already uses to
	build an employee's `lms_roles` list, so this stays consistent with
	the rest of the app's definition rather than inventing a second one.
	"""
	relevant_roles = frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ["like", "LMS%"]},
		pluck="parent",
	) + frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ["in", ["Course Creator", "Moderator", "Batch Evaluator"]]},
		pluck="parent",
	)
	if not relevant_roles:
		return []

	return frappe.get_all(
		"User", filters={"name": ["in", set(relevant_roles)], "enabled": 1}, pluck="name"
	)


def _dispatch(action, folder_doc):
	settings = frappe.db.get_singles_dict("LMS Settings")
	send_email = cint(settings.get("notify_resource_updates_by_email"))
	send_in_app = cint(settings.get("notify_resource_updates_in_app"))
	if not send_email and not send_in_app:
		return

	recipients = get_lms_notification_recipients()
	if not recipients:
		return

	if send_email:
		_send_email(action, folder_doc, recipients)
	if send_in_app:
		_send_system_notification(action, folder_doc, recipients)


def _send_email(action, folder_doc, recipients):
	subject = _("Folder {0} was {1}").format(folder_doc.file_name, action)
	args = {
		"action": action,
		"folder": folder_doc.file_name,
		"resource_url": f"{frappe.utils.get_url()}/lms/resources/{folder_doc.name}",
	}
	frappe.enqueue(
		method=frappe.sendmail,
		queue="short",
		timeout=300,
		is_async=True,
		recipients=recipients,
		subject=subject,
		template="resource_updated",
		args=args,
	)


def _send_system_notification(action, folder_doc, recipients):
	notification = frappe._dict(
		{
			"subject": _("Folder {0} was {1}").format(folder_doc.file_name, action),
			"email_content": _("The folder '{0}' was {1}. Check it out!").format(
				folder_doc.file_name, action
			),
			"document_type": "File",
			"document_name": folder_doc.name,
			"from_user": frappe.session.user,
			"type": "Alert",
			"link": f"/lms/resources/{folder_doc.name}",
		}
	)
	make_notification_logs(notification, recipients)
