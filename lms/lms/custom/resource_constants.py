import frappe
from frappe import _
from frappe.utils import getdate, today

RESOURCE_ROOT_FOLDER = "Home/LMS Resources"

ALLOWED_RESOURCE_EXTENSIONS = {"PDF", "PPT", "PPTX"}
MAX_RESOURCE_FILE_SIZE = 25 * 1024 * 1024  # 25 MB - matches Frappe's own default max upload size (get_max_file_size)


def validate_resource_file(file_name, size):
	"""Enforce the Resources feature's own file-type allow-list and size cap
	on the actual uploaded content - independent of System Settings'
	"Allowed File Extensions", which imposes no restriction at all unless an
	admin has explicitly populated it (frappe/core/doctype/file/file.py
	validate_file_extension() no-ops when that setting is empty, which it is
	by default).

	Shared by resource_api.replace_resource_file (checked before any byte is
	written) and the File.validate doc_event hook (covers the initial
	Upload File button too, which goes through Frappe's generic upload_file
	endpoint, not through resource_api.py) - so neither path can be used to
	plant an HTML/SVG file that stream_resource would later serve inline,
	in-origin.
	"""
	extension = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").upper()
	if extension not in ALLOWED_RESOURCE_EXTENSIONS:
		frappe.throw(_("Only PDF and PPT/PPTX files are allowed as Resources."))
	if size > MAX_RESOURCE_FILE_SIZE:
		frappe.throw(
			_("File exceeds the maximum allowed size of {0} MB.").format(
				MAX_RESOURCE_FILE_SIZE // (1024 * 1024)
			)
		)


def is_under_resource_root(folder):
	"""True if `folder` is RESOURCE_ROOT_FOLDER or nested anywhere under it."""
	while folder:
		if folder == RESOURCE_ROOT_FOLDER:
			return True
		folder = frappe.db.get_value("File", folder, "folder")
	return False


def get_top_level_folder(folder):
	"""Given a File's immediate `folder` (its parent docname), walk up to
	the direct child of RESOURCE_ROOT_FOLDER and return that folder's own
	docname - the "main folder" (e.g. "Sports"), never a deeper subfolder
	and never RESOURCE_ROOT_FOLDER itself. Returns None if `folder` *is*
	RESOURCE_ROOT_FOLDER (the file sits directly in the root, so there is
	no main folder to show).
	"""
	if not folder or folder == RESOURCE_ROOT_FOLDER:
		return None
	current = folder
	while True:
		parent = frappe.db.get_value("File", current, "folder")
		if not parent or parent == RESOURCE_ROOT_FOLDER:
			return current
		current = parent


def is_effectively_published(name):
	"""True only if `name` (a file or folder) AND every ancestor folder up
	to and including RESOURCE_ROOT_FOLDER are published, AND none of them
	has a future `publish_on` date still pending. A single unpublished
	(or not-yet-scheduled) link anywhere in the chain hides everything
	below it - an AND-gate, not "nearest explicit value wins" like
	get_effective_download_permission.

	`publish_on` is optional: blank means "publish immediately" (as soon
	as `published` is checked); a future date means "wanted published,
	but not visible until that date arrives" - visibility here re-derives
	live on every call, so nothing needs to flip automatically for this
	part. (The notification that should fire when that date arrives is a
	separate concern - see resource_notify.send_scheduled_publish_notifications,
	since nothing saves the document on that day to trigger a doc_event.)

	Stops at RESOURCE_ROOT_FOLDER deliberately - Frappe's generic "Home"
	folder above it was never meant to be published/unpublished by an
	admin and would otherwise always evaluate false.
	"""
	current = name
	while current:
		published, publish_on = frappe.db.get_value("File", current, ["published", "publish_on"])
		if not published:
			return False
		if publish_on and getdate(publish_on) > getdate(today()):
			return False
		if current == RESOURCE_ROOT_FOLDER:
			break
		current = frappe.db.get_value("File", current, "folder")
	return True
