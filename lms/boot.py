import frappe


def boot_session(bootinfo):
	"""Filter apps shown on the apps page to only show LMS"""
	# This is called after all apps are added, so we filter here
	pass


def extend_bootinfo(bootinfo):
	"""Override apps list to show only LMS"""
	# Remove all apps except LMS from the bootinfo
	if "apps" in bootinfo:
		bootinfo["apps"] = [app for app in bootinfo["apps"] if app.get("name") == "lms"]


@frappe.whitelist()
def get_apps_override():
	"""Override get_apps to only return LMS app"""
	from frappe.apps import get_route

	# Only return the LMS app
	lms_details = frappe.get_hooks("add_to_apps_screen", app_name="lms")

	if not lms_details:
		return []

	app_list = []
	for app_detail in lms_details:
		app_list.append({
			"name": "lms",
			"logo": app_detail.get("logo"),
			"title": frappe._(app_detail.get("title")),
			"route": app_detail.get("route", "/lms"),
		})

	return app_list
