import frappe


def execute():
	frappe.db.set_single_value("LMS Settings", "notify_resource_updates_by_email", True)
	frappe.db.set_single_value("LMS Settings", "notify_resource_updates_in_app", True)
