# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Batch Enrollment Approval System

This module implements manager approval workflow for batch enrollments,
allowing managers to approve/reject enrollments of their direct reports.
"""

import frappe
from frappe import _


def add_batch_enrollment_approval_fields():
	"""Add custom fields for manager approval workflow to LMS Batch Enrollment"""

	custom_fields = {
		"LMS Batch Enrollment": [
			{
				"fieldname": "approval_section",
				"fieldtype": "Section Break",
				"label": _("Manager Approval"),
				"insert_after": "batch",
				"collapsible": 1,
			},
			{
				"fieldname": "employee",
				"fieldtype": "Link",
				"label": _("Employee"),
				"options": "Employee",
				"insert_after": "approval_section",
				"read_only": 1,
				"in_list_view": 0,
			},
			{
				"fieldname": "employee_name",
				"fieldtype": "Data",
				"label": _("Employee Name"),
				"insert_after": "employee",
				"fetch_from": "employee.employee_name",
				"read_only": 1,
				"in_list_view": 0,
			},
			{
				"fieldname": "column_break_approval",
				"fieldtype": "Column Break",
				"insert_after": "employee_name",
			},
			{
				"fieldname": "approval_status",
				"fieldtype": "Select",
				"label": _("Approval Status"),
				"options": "\nPending\nApproved\nRejected",
				"default": "Pending",
				"insert_after": "column_break_approval",
				"in_list_view": 1,
				"in_standard_filter": 1,
			},
			{
				"fieldname": "approved_by",
				"fieldtype": "Link",
				"label": _("Approved By"),
				"options": "User",
				"insert_after": "approval_status",
				"read_only": 1,
			},
			{
				"fieldname": "approval_date",
				"fieldtype": "Datetime",
				"label": _("Approval Date"),
				"insert_after": "approved_by",
				"read_only": 1,
			},
			{
				"fieldname": "manager_comments",
				"fieldtype": "Text Editor",
				"label": _("Manager Comments"),
				"insert_after": "approval_date",
			},
		],
	}

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	print("✓ Batch enrollment approval custom fields added successfully")


def get_manager_permission_query_condition(user, doctype):
	"""
	Permission query to show only enrollments of direct reports to managers

	This function filters enrollments so that:
	1. Users see their own enrollments
	2. Managers see enrollments of their direct reports
	3. System Manager, Moderator, and Course Creator see all enrollments
	"""
	try:
		if not user:
			user = frappe.session.user

		# System Manager, Moderator, and Course Creator can see all
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles(user):
			return None

		if "Moderator" in frappe.get_roles(user) or "Course Creator" in frappe.get_roles(user):
			return None

		# Get current user's employee record
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

		if not employee:
			# If user is not an employee, show only their own enrollments
			return f"`tab{doctype}`.member = {frappe.db.escape(user)}"

		# Get all employees who report to this manager (directly or indirectly)
		reporting_employees = get_all_reporting_employees(employee)

		# Get user IDs for all reporting employees
		reporting_users = frappe.db.sql_list(
			"""
			SELECT user_id
			FROM `tabEmployee`
			WHERE name IN %s AND user_id IS NOT NULL
			""",
			[reporting_employees],
		)

		# Add the current user to the list
		reporting_users.append(user)

		# Return condition to show enrollments of reporting employees and self
		if reporting_users:
			users_list = ", ".join([frappe.db.escape(u) for u in reporting_users])
			return f"`tab{doctype}`.member IN ({users_list})"

		# Default: show only own enrollments
		return f"`tab{doctype}`.member = {frappe.db.escape(user)}"
	except Exception as e:
		# Log error but don't break permission check - default to showing only own
		frappe.log_error(
			f"Error in manager permission query: {str(e)}", "Batch Enrollment Approval Permission"
		)
		return f"`tab{doctype}`.member = {frappe.db.escape(user)}"


def get_all_reporting_employees(employee, employees_list=None):
	"""
	Recursively get all employees reporting to a manager (direct and indirect reports)
	"""
	if employees_list is None:
		employees_list = []

	# Get direct reports
	direct_reports = frappe.db.sql_list(
		"""
		SELECT name
		FROM `tabEmployee`
		WHERE reports_to = %s AND status = 'Active'
		""",
		employee,
	)

	for report in direct_reports:
		if report not in employees_list:
			employees_list.append(report)
			# Recursively get their reports
			get_all_reporting_employees(report, employees_list)

	return employees_list


def has_permission(doc, ptype, user):
	"""
	Additional permission check for enrollments

	Returns True if:
	1. User is the owner of enrollment
	2. User is a manager of the employee who created the enrollment
	3. User has Moderator/System Manager role
	"""
	if not user:
		user = frappe.session.user

	# System Manager, Moderator, and Course Creator have full access
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if "Moderator" in frappe.get_roles(user) or "Course Creator" in frappe.get_roles(user):
		return True

	# Owner can access their own enrollment
	if doc.member == user:
		return True

	# Check if user is a manager of the enrollment owner
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return False

	# Get employee of enrollment owner
	enrollment_employee = frappe.db.get_value("Employee", {"user_id": doc.member}, "name")
	if not enrollment_employee:
		return False

	# Check if enrollment employee reports to current user's employee
	reporting_employees = get_all_reporting_employees(employee)

	return enrollment_employee in reporting_employees


@frappe.whitelist()
def approve_enrollment(name, comments=None):
	"""
	Approve a batch enrollment by manager

	Args:
		name: Name of the LMS Batch Enrollment document
		comments: Optional manager comments
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Not allowed"))

	doc = frappe.get_doc("LMS Batch Enrollment", name)

	# Check if user is authorized to approve
	if not can_manage_enrollment(doc):
		frappe.throw(_("You are not authorized to approve this enrollment"))

	# Track previous status for notification
	previous_status = doc.approval_status

	# Update approval fields
	doc.approval_status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approval_date = frappe.utils.now()
	if comments:
		doc.manager_comments = comments

	doc.save(ignore_permissions=True)

	# Send notification to employee
	action = "re-approved" if previous_status == "Approved" else "approved"
	send_approval_notification(doc, action, previous_status)

	message = (
		_("Enrollment re-approved successfully")
		if previous_status == "Approved"
		else _("Enrollment approved successfully")
	)
	return {"success": True, "message": message, "doc": doc}


@frappe.whitelist()
def reject_enrollment(name, comments=None):
	"""
	Reject a batch enrollment by manager

	Args:
		name: Name of the LMS Batch Enrollment document
		comments: Optional manager comments (recommended for rejection)
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Not allowed"))

	doc = frappe.get_doc("LMS Batch Enrollment", name)

	# Check if user is authorized to reject
	if not can_manage_enrollment(doc):
		frappe.throw(_("You are not authorized to reject this enrollment"))

	# Track previous status for notification
	previous_status = doc.approval_status

	# Update approval fields
	doc.approval_status = "Rejected"
	doc.approved_by = frappe.session.user
	doc.approval_date = frappe.utils.now()
	if comments:
		doc.manager_comments = comments

	doc.save(ignore_permissions=True)

	# Send notification to employee
	action = "re-rejected" if previous_status == "Rejected" else "rejected"
	send_approval_notification(doc, action, previous_status)

	message = (
		_("Enrollment status updated to rejected")
		if previous_status == "Rejected"
		else _("Enrollment rejected")
	)
	return {"success": True, "message": message, "doc": doc}


def can_manage_enrollment(doc):
	"""Check if current user can approve/reject this enrollment"""
	user = frappe.session.user

	# System Manager, Moderator can manage
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if "Moderator" in frappe.get_roles(user):
		return True

	# Check if user is manager of enrollment owner
	manager_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not manager_employee:
		return False

	enrollment_employee = frappe.db.get_value("Employee", {"user_id": doc.member}, "name")
	if not enrollment_employee:
		return False

	# Check if enrollment employee reports to current user
	reporting_employees = get_all_reporting_employees(manager_employee)

	return enrollment_employee in reporting_employees


def send_approval_notification(doc, action, previous_status=None):
	"""Send notification to employee about approval/rejection"""
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	# Create appropriate message based on action and previous status
	if action == "approved":
		subject = _("Your batch enrollment has been approved by your manager")
		color = "green"
	elif action == "re-approved":
		subject = _("Your batch enrollment approval has been updated")
		color = "green"
	elif action == "rejected":
		subject = _("Your batch enrollment has been rejected by your manager")
		color = "red"
	elif action == "re-rejected":
		subject = _("Your batch enrollment has been reviewed again")
		color = "orange"
	else:
		subject = _("Your batch enrollment status has been updated")
		color = "blue"

	# Add context about status change if applicable
	email_content = doc.manager_comments or ""
	if previous_status and previous_status != doc.approval_status:
		status_change = _("Status changed from {0} to {1}").format(
			previous_status, doc.approval_status
		)
		email_content = f"{status_change}\n\n{email_content}" if email_content else status_change

	notification = frappe._dict(
		{
			"subject": subject,
			"email_content": email_content,
			"document_type": doc.doctype,
			"document_name": doc.name,
			"from_user": doc.approved_by,
			"type": "Alert",
			"color": color,
		}
	)

	make_notification_logs(notification, [doc.member])


def set_employee_field(doc, method=None):
	"""Automatically set employee field based on member (user) field"""
	if not doc.member:
		return

	# Get employee linked to this user
	employee = frappe.db.get_value("Employee", {"user_id": doc.member}, "name")
	if employee:
		doc.employee = employee

	# Set default approval status if not set
	if not doc.approval_status:
		doc.approval_status = "Pending"
