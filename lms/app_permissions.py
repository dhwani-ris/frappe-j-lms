import frappe
import json


def block_other_apps():
	"""Block all apps except LMS from showing on apps page"""
	return False


def check_app_permission_for_erpnext():
	"""Permission check for ERPNext app - hide it"""
	return False


def check_app_permission_for_hrms():
	"""Permission check for HRMS app - hide it"""
	return False


def check_app_permission_for_insights():
	"""Permission check for Insights app - hide it"""
	return False


def filter_importable_doctypes(user):
	"""Filter DocTypes in Data Import dropdown to show only LMS, Employee, and User doctypes"""
	# Always filter to LMS-related DocTypes + User + Employee for all contexts
	# This is acceptable since we only use DocType queries in data import context in LMS app
	allowed_doctypes = [
		"User",
		"Employee",
		# LMS DocTypes
		"LMS Course",
		"LMS Batch",
		"LMS Batch Enrollment",
		"LMS Enrollment",
		"LMS Quiz",
		"LMS Quiz Question",
		"LMS Quiz Submission",
		"LMS Assignment",
		"LMS Assignment Submission",
		"LMS Certificate",
		"LMS Certificate Evaluation",
		"LMS Certificate Request",
		"LMS Chapter",
		"LMS Class",
		"LMS Course Mentor Mapping",
		"LMS Course Progress",
		"LMS Exercise",
		"LMS Live Class",
		"LMS Message",
		"LMS Student Progress Alert",
		"LMS Payment",
	]

	return f"`tabDocType`.name in ({', '.join(repr(dt) for dt in allowed_doctypes)})"


@frappe.whitelist()
def search_link_override(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
):
	"""Override search_link to filter DocTypes in Data Import"""
	# Debug logging
	print(f"\n\n=== search_link_override called ===")
	print(f"doctype: {doctype}")
	print(f"filters: {filters}")
	print(f"txt: {txt}")
	print("=" * 50)

	# Parse filters if it's a string
	parsed_filters = filters
	if isinstance(filters, str):
		try:
			parsed_filters = json.loads(filters)
		except:
			parsed_filters = {}

	# If searching for DocType with allow_import filter, apply our custom filter
	if doctype == "DocType" and parsed_filters and isinstance(parsed_filters, dict) and parsed_filters.get("allow_import") == 1:
		# Add our allowed DocTypes filter
		allowed_doctypes = [
			"User",
			"Employee",
			"LMS Course",
			"LMS Batch",
			"LMS Batch Enrollment",
			"LMS Enrollment",
			"LMS Quiz",
			"LMS Quiz Question",
			"LMS Quiz Submission",
			"LMS Assignment",
			"LMS Assignment Submission",
			"LMS Certificate",
			"LMS Certificate Evaluation",
			"LMS Certificate Request",
			"LMS Chapter",
			"LMS Class",
			"LMS Course Mentor Mapping",
			"LMS Course Progress",
			"LMS Exercise",
			"LMS Live Class",
			"LMS Message",
			"LMS Student Progress Alert",
			"LMS Payment",
		]

		# Add the name filter to restrict to allowed doctypes
		parsed_filters["name"] = ["in", allowed_doctypes]
		# Convert back to JSON string for the original method
		filters = json.dumps(parsed_filters)

	# Call the original method
	from frappe.desk.search import search_link as original_search_link
	return original_search_link(
		doctype=doctype,
		txt=txt,
		query=query,
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)
