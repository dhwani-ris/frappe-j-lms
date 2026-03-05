import frappe


def boot_session(bootinfo):
	"""Filter apps shown on the apps page to only show LMS"""
	if "apps" in bootinfo:
		# Keep only the LMS app
		bootinfo["apps"] = [app for app in bootinfo["apps"] if app.get("name") == "lms"]
