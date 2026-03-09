import frappe


def boot_session(bootinfo):
	"""Filter apps shown on the apps page to only show LMS"""
	pass


def extend_bootinfo(bootinfo):
	"""Override apps list to show only LMS"""
	# Remove all apps except LMS from the bootinfo
	if "apps" in bootinfo:
		bootinfo["apps"] = [app for app in bootinfo["apps"] if app.get("name") == "frappe_lms"]


@frappe.whitelist()
def get_apps_override():
	"""Override get_apps to only return LMS app"""
	from frappe.apps import get_route
	from frappe.desk.desktop import get_workspace_sidebar_items

	allowed_workspaces = get_workspace_sidebar_items().get("pages")

	# Only return the LMS app (frappe_lms)
	lms_details = frappe.get_hooks("add_to_apps_screen", app_name="frappe_lms")

	if not lms_details:
		return []

	app_list = []
	for app_detail in lms_details:
		app_list.append({
			"name": "frappe_lms",
			"logo": app_detail.get("logo"),
			"title": frappe._(app_detail.get("title")),
			"route": get_route(app_detail, allowed_workspaces),
		})

	return app_list
