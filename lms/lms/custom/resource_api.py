import os
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.utils import cint

from lms.lms.custom.resource_constants import (
	RESOURCE_ROOT_FOLDER,
	is_effectively_published,
	is_under_resource_root,
	validate_resource_file,
)
from lms.lms.custom.resource_notify import notify_resource_change

RESOURCE_MANAGER_ROLES = {"Moderator", "Course Creator", "LMS Master Trainer", "System Manager"}

# PPT/PPTX have no browser-native inline renderer at all, unlike PDF -
# converted to PDF on the fly for viewing only (see stream_resource).
# Legacy .ppt and modern .pptx both convert fine through the same
# headless LibreOffice call; Download still always serves the original
# file untouched, never a converted copy.
CONVERTIBLE_TO_PDF_TYPES = {"PPT", "PPTX"}


def is_resource_manager(user=None):
	"""Who's allowed to manage Resources (and see drafts of them) -
	deliberately role-based, NOT frappe.has_permission("File", "write").

	Confirmed by testing (a plain employee could see draft Resources):
	this site has a Custom DocPerm granting the "All" role - which every
	logged-in user automatically has - write access on File. That's a
	pre-existing site customization (likely so generic attachments work
	broadly elsewhere in the app), completely unrelated to anything built
	here, but it meant frappe.has_permission("File", "write") was
	effectively True for *everyone*, not just real managers - silently
	defeating the draft-visibility gate (and, worse, the manage-Resources
	guard on replace/delete too).

	Mirrors the exact role set Resources.vue's own `canManage` check
	already uses (is_moderator/is_instructor/is_master_trainer) - so
	admin-UI visibility and backend enforcement now agree with each
	other. They didn't before this fix: a Moderator or Course Creator
	without the System Manager role would see the management controls in
	the UI but get silently denied by the backend when actually using
	them, since the old check only really tracked System Manager (File's
	base role permissions) rather than "All" (Custom DocPerm) unless
	prompted otherwise - this redefinition fixes both issues at once.
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & RESOURCE_MANAGER_ROLES)


def has_resource_permission(doc, ptype=None, user=None, debug=False):
	"""Grants read/select on files under the Resources folder tree to any
	enabled, logged-in user - PROVIDED the file (and every ancestor folder)
	is published. Unpublished/draft resources are only readable by
	managers.

	Necessary because Frappe's default File permission model
	(frappe/core/doctype/file/file.py has_permission) only grants a
	non-owner access via explicit DocShare or a readable
	attached_to_doctype - neither applies to standalone library files like
	these, so without this hook every non-admin user is silently denied
	read access to every Resource (confirmed during testing: a test
	employee account could see files listed via get_folder_contents,
	which uses frappe.get_all and so bypasses permission filtering
	entirely, but View/Download failed silently because those go through
	frappe.client.get / has_permission, which does enforce it).

	Returns None (defer to Frappe's own default) for anything outside
	Resources, for Guest, or for any ptype other than read/select - so
	this can't affect any other file on the site, and can't be used to
	loosen who is allowed to manage (write/delete) Resources. Returns an
	explicit False (not None) for an unpublished resource viewed by a
	non-manager, to guarantee the block regardless of any other permission
	path (e.g. accidental ownership) that might otherwise apply.
	"""
	if ptype not in ("read", "select"):
		return None
	if not user or user == "Guest":
		return None

	folder = doc.name if doc.is_folder else doc.folder
	if not is_under_resource_root(folder):
		return None

	if is_effectively_published(doc.name):
		return True

	return True if is_resource_manager(user) else False


@frappe.whitelist()
def get_folder_contents(folder=None):
	"""Direct children (subfolders and files) of a Resources folder, each
	annotated with whether it can currently be downloaded and, for files,
	whether a quiz is attached. Used by the Resources page instead of a
	raw list call so permission resolution stays server-side, not
	duplicated in the frontend.

	Non-managers never see a draft (not effectively published) folder or
	file - filtered out here entirely, not just hidden in the UI.
	Managers see everything, including drafts, so they can review/publish
	them; `published` is returned per item either way so the frontend can
	show a Draft badge and the publish toggle.
	"""
	folder = folder or RESOURCE_ROOT_FOLDER
	ensure_resource_root()

	items = frappe.get_all(
		"File",
		filters={"folder": folder},
		fields=[
			"name",
			"file_name",
			"file_url",
			"file_type",
			"file_size",
			"is_folder",
			"download_permission",  # only meaningful when is_folder=1
			"published",
			"publish_on",
			"owner",
			"modified",
		],
		order_by="is_folder desc, file_name asc",
	)

	manager = is_resource_manager()
	if not manager:
		items = [item for item in items if is_effectively_published(item.name)]

	for item in items:
		_annotate_item(item)

	return items


@frappe.whitelist()
def search_resources(query):
	"""Search every file AND folder under the Resources tree by name,
	regardless of nesting depth - unlike get_folder_contents, which only
	lists one folder's direct children. Matches how a real document
	library search is expected to behave (find it anywhere, not just in
	the folder you happen to already be browsing) - folders are included
	too, since someone might remember a folder's name without remembering
	where it's nested.

	`folder = ROOT or folder LIKE 'ROOT/%'` is a cheap prefix match that
	naturally covers every nested subfolder without a recursive query,
	since a folder's own docname IS its full path (e.g.
	"Home/LMS Resources/Product Updates/India"). This also naturally
	excludes RESOURCE_ROOT_FOLDER itself from ever appearing as a result
	(its own `folder` is "Home", matching neither condition) - correct,
	since it's the technical bootstrap container, not a real searchable
	item.

	Applies the exact same publish-visibility rule as get_folder_contents -
	search can't be used to find drafts that browsing wouldn't show you.
	Capped at 50 results - a search box returning thousands of rows isn't
	useful anyway; narrow the query instead.
	"""
	query = (query or "").strip()
	if not query:
		return []

	ensure_resource_root()

	items = frappe.get_all(
		"File",
		filters=[
			["file_name", "like", f"%{query}%"],
		],
		or_filters=[
			["folder", "=", RESOURCE_ROOT_FOLDER],
			["folder", "like", f"{RESOURCE_ROOT_FOLDER}/%"],
		],
		fields=[
			"name",
			"file_name",
			"file_url",
			"file_type",
			"file_size",
			"is_folder",
			"folder",
			"download_permission",
			"published",
			"publish_on",
			"owner",
			"modified",
		],
		order_by="is_folder desc, file_name asc",
		limit_page_length=50,
	)

	manager = is_resource_manager()
	if not manager:
		items = [item for item in items if is_effectively_published(item.name)]

	for item in items:
		_annotate_item(item)
		# Search spans folders, so (unlike normal browsing, where you're
		# already standing inside the relevant folder) each result needs
		# to say where it lives.
		item["folder_label"] = item.folder.split("/")[-1] if item.folder else ""

	return items


def _annotate_item(item):
	"""Shared per-item computed fields for get_folder_contents and
	search_resources, so the two stay in sync rather than drifting."""
	# Server-computed so the frontend can show an accurate Draft vs.
	# Scheduled vs. live badge without re-implementing the AND-gate walk
	# (own + every ancestor folder) in JS.
	item["is_live"] = is_effectively_published(item.name)

	if item.is_folder:
		item["can_download"] = True
		item["quiz"] = None
		item["viewed"] = False
	else:
		item["can_download"] = get_effective_download_permission(item.name)
		item["quiz"] = frappe.db.get_value(
			"LMS Quiz", {"resource": item.name}, ["name", "title"], as_dict=True
		)
		item["viewed"] = bool(
			frappe.db.exists(
				"View Log",
				{
					"reference_doctype": "File",
					"reference_name": item.name,
					"viewed_by": frappe.session.user,
				},
			)
		)


def ensure_resource_root():
	"""Create the root 'LMS Resources' folder the first time it's needed,
	so the feature works out of the box without a manual setup step.
	Published by default - only content inside it starts as a draft.

	Self-heals an existing root created before the `published` field
	existed (confirmed during testing: a root folder from an earlier
	session sat at published=0 - the field's default for any
	already-existing row, since a Custom Field's default only applies
	going forward, not retroactively - which would have blocked
	everything under Resources for every non-manager via the AND-gate,
	regardless of their own individual publish state).
	"""
	if frappe.db.exists("File", RESOURCE_ROOT_FOLDER):
		if not frappe.db.get_value("File", RESOURCE_ROOT_FOLDER, "published"):
			frappe.db.set_value("File", RESOURCE_ROOT_FOLDER, "published", 1)
		return
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": "LMS Resources",
			"is_folder": 1,
			"folder": "Home",
			"published": 1,
		}
	).insert(ignore_permissions=True)


@frappe.whitelist()
def replace_resource_file(file_name):
	"""Replace an existing Resource document's content in place.

	Expects the new file posted as multipart/form-data under the 'file'
	key (same convention Frappe's own upload_file endpoint uses),
	alongside `file_name` identifying which existing File record to
	overwrite.

	Uses Frappe's own File.save_file(overwrite=True) - built for exactly
	this. The record keeps the same name/docname throughout, so any LMS
	Quiz.resource pointing at it stays valid automatically; no
	delete-and-relink needed. (Confirmed during implementation: private
	File names are random hashes, not content-derived - see decision.md #10,
	updated.)
	"""
	_check_resource_admin()

	uploaded_file = frappe.request.files["file"]
	content = uploaded_file.stream.read()
	validate_resource_file(uploaded_file.filename, len(content))

	doc = frappe.get_doc("File", file_name)
	doc.file_name = uploaded_file.filename
	doc.save_file(content=content, overwrite=True)
	doc.save(ignore_permissions=True)

	notify_resource_change(doc, method="replace")

	return doc.name


@frappe.whitelist()
def create_resource_folder(folder, file_name):
	"""Create a subfolder under the Resources tree.

	Must not be exposed as a raw frappe.client.insert call from the
	frontend: this site's File doctype has a pre-existing Custom DocPerm
	granting the "All" role write access (see is_resource_manager's
	docstring), so the generic RPC's own permission check would let any
	logged-in user create folders anywhere, not just Resource Managers
	under Resources.
	"""
	_check_resource_admin()

	folder = folder or RESOURCE_ROOT_FOLDER
	if not is_under_resource_root(folder):
		frappe.throw(_("Invalid folder."), frappe.PermissionError)

	doc = frappe.get_doc(
		{
			"doctype": "File",
			"is_folder": 1,
			"folder": folder,
			"file_name": file_name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _get_scoped_resource(file_name):
	"""Load a File doc, but only if it's actually under the Resources
	tree - so a Resource Manager's admin actions can't be pointed at an
	arbitrary File record elsewhere on the site."""
	doc = frappe.get_doc("File", file_name)
	folder = doc.name if doc.is_folder else doc.folder
	if not is_under_resource_root(folder):
		frappe.throw(_("Not a Resource."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def set_resource_download_permission(file_name, value):
	_check_resource_admin()
	doc = _get_scoped_resource(file_name)
	doc.download_permission = value
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def set_resource_published(file_name, value):
	_check_resource_admin()
	doc = _get_scoped_resource(file_name)
	doc.published = cint(value)
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def set_resource_publish_on(file_name, value):
	_check_resource_admin()
	doc = _get_scoped_resource(file_name)
	doc.publish_on = value or None
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def delete_resource(file_name):
	_check_resource_admin()
	_get_scoped_resource(file_name)
	frappe.delete_doc("File", file_name, ignore_permissions=True)


def validate_resource_upload(doc, method=None):
	"""File.validate doc_event hook (registered in hooks.py) - enforces the
	Resources feature's file-type allow-list and size cap on every File
	saved under the Resources tree, regardless of which endpoint
	created/updated it. Necessary because the initial Upload File button
	(Resources.vue's FileUploader) goes through Frappe's own generic
	upload_file endpoint, not through resource_api.py, so
	replace_resource_file's own check alone wouldn't cover a first-time
	upload of a disallowed file.
	"""
	if doc.is_folder:
		return
	if not is_under_resource_root(doc.folder):
		return
	validate_resource_file(doc.file_name, doc.file_size or 0)


def get_effective_download_permission(file_name):
	"""Resolve whether a file can be downloaded, or only viewed.

	This setting is folder-only by design (never set on an individual
	file) - starts at the file's parent folder and walks up the folder
	chain, returning the first explicit value found. Defaults to allowed
	(True) if nothing in the chain has been explicitly set.
	"""
	current = frappe.db.get_value("File", file_name, "folder")
	while current:
		value = frappe.db.get_value("File", current, "download_permission")
		if value:
			return value != "View Only"
		current = frappe.db.get_value("File", current, "folder")
	return True


@frappe.whitelist()
def mark_resource_viewed(file_name):
	"""Records that the current user has opened/downloaded this resource.

	Deliberately explicit rather than relying on Frappe's own View Log
	auto-logging: that only fires from frappe.desk.form.load.getdoc() (the
	Desk UI's own document-open endpoint) via Document.add_viewed() -
	confirmed by tracing Frappe core, the ONLY caller of add_viewed() in
	the whole framework besides this is the newsletter open-tracker.
	Generic API calls like frappe.client.get never trigger it, so simply
	turning on track_views (as originally planned) was never actually
	going to log anything on its own - this whitelisted method calls
	add_viewed() itself instead, so it happens reliably regardless of
	which underlying Frappe API path serves the actual file.

	unique_views=True keeps this idempotent - re-viewing/re-downloading
	the same file doesn't pile up duplicate View Log rows, and the
	resource-gated quiz check only cares whether at least one row exists.
	"""
	if not frappe.has_permission("File", "read", doc=file_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	frappe.get_doc("File", file_name).add_viewed(force=True, unique_views=True)


@frappe.whitelist()
def stream_resource(file_name, as_attachment=0):
	"""Serves a Resource file's actual bytes for View/Download.

	Deliberately does NOT hand back a raw file_url for the browser to
	fetch directly - Frappe's native private-file route
	(download_private_file -> find_file_by_url -> File.is_downloadable())
	calls frappe.core.doctype.file.file.has_permission() as a plain
	Python function call, bypassing the has_permission hooks pipeline
	entirely. Our has_resource_permission hook above is therefore never
	consulted on that route, and every non-admin user gets a hard
	"Forbidden" there regardless of this feature's own rules (confirmed
	during testing - Administrator worked because file.py's has_permission
	special-cases Administrator directly; a real employee account did not).

	This endpoint instead checks frappe.has_permission() itself - which
	DOES run the full hook pipeline - then reads and returns the content
	directly, so the browser never touches the native route at all.
	"""
	as_attachment = cint(as_attachment)

	if not frappe.has_permission("File", "read", doc=file_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if as_attachment and not get_effective_download_permission(file_name):
		frappe.throw(_("This document is view-only and cannot be downloaded."))

	file_doc = frappe.get_doc("File", file_name)
	file_doc.add_viewed(force=True, unique_views=True)  # defense in depth - see mark_resource_viewed

	if not as_attachment and file_doc.file_type in CONVERTIBLE_TO_PDF_TYPES:
		# Viewing (not downloading) a PPT/PPTX - convert to PDF on the fly
		# so it renders in the same inline viewer as a real PDF, instead
		# of handing the browser a format nothing can display natively.
		# Download (as_attachment=1) never goes through this branch - it
		# always serves the original file untouched, since converting
		# there would hand back a PDF when the person asked to download
		# the actual, editable PowerPoint file.
		frappe.local.response.filename = os.path.splitext(file_doc.file_name)[0] + ".pdf"
		frappe.local.response.filecontent = _convert_to_pdf(file_doc)
		frappe.local.response.type = "download"
		frappe.local.response.display_content_as = "inline"
		return

	frappe.local.response.filename = file_doc.file_name
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "attachment" if as_attachment else "inline"


def _convert_to_pdf(file_doc):
	"""Converts a PPT/PPTX file to PDF via headless LibreOffice (the
	`soffice` CLI, confirmed installed and working for both legacy .ppt
	and modern .pptx). Runs in an isolated temp profile
	(-env:UserInstallation) so concurrent conversions from different
	users don't collide over LibreOffice's shared user-profile lock - a
	known issue when running multiple headless instances at once.
	"""
	with tempfile.TemporaryDirectory() as tmpdir:
		input_path = file_doc.get_full_path()
		profile_dir = os.path.join(tmpdir, "profile")

		try:
			subprocess.run(
				[
					"soffice",
					"--headless",
					"--norestore",
					f"-env:UserInstallation=file://{profile_dir}",
					"--convert-to",
					"pdf",
					"--outdir",
					tmpdir,
					input_path,
				],
				capture_output=True,
				timeout=60,
				check=True,
			)
		except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
			frappe.throw(_("Could not generate a preview for this document. Try downloading it instead."))

		base_name = os.path.splitext(os.path.basename(input_path))[0]
		pdf_path = os.path.join(tmpdir, f"{base_name}.pdf")
		if not os.path.exists(pdf_path):
			frappe.throw(_("Could not generate a preview for this document. Try downloading it instead."))

		with open(pdf_path, "rb") as f:
			return f.read()


def _check_resource_admin():
	if not is_resource_manager():
		frappe.throw(_("You are not permitted to manage Resources."), frappe.PermissionError)
