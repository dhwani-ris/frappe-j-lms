import frappe
from frappe.desk.page.setup_wizard.setup_wizard import add_all_roles_to

from lms.lms.api import give_discussions_permission
from lms.lms.custom.jamboree_setup import setup_jamboree_roles


def after_install():
	create_batch_source()
	give_discussions_permission()


def after_sync():
	create_lms_roles()
	set_default_certificate_print_format()
	setup_jamboree_roles()
	setup_feedback_event_custom_fields()
	give_lms_roles_to_admin()


def setup_feedback_event_custom_fields():
	"""Hidden back-link fields on Event so the Employee Feedback calendar sync can reconcile
	a form's session events (one query per form) and do clean update/cancel. Idempotent."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Event": [
				{
					"fieldname": "custom_feedback_form",
					"label": "Employee Feedback Form",
					"fieldtype": "Link",
					"options": "Employee Feedback Form",
					"insert_after": "description",
					"hidden": 1,
					"read_only": 1,
					"no_copy": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "custom_feedback_key",
					"label": "Feedback Session Key",
					"fieldtype": "Data",
					"insert_after": "custom_feedback_form",
					"hidden": 1,
					"read_only": 1,
					"no_copy": 1,
					"print_hide": 1,
				},
			]
		},
		ignore_validate=True,
	)


def before_uninstall():
	delete_custom_fields()
	delete_lms_roles()


def create_lms_roles():
	create_course_creator_role()
	create_moderator_role()
	create_evaluator_role()
	create_lms_student_role()


def delete_lms_roles():
	roles = ["Course Creator", "Moderator"]
	for role in roles:
		if frappe.db.exists("Role", role):
			frappe.db.delete("Role", role)


def create_course_creator_role():
	if frappe.db.exists("Role", "Course Creator"):
		frappe.db.set_value("Role", "Course Creator", "desk_access", 0)
	else:
		role = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "Course Creator",
				"home_page": "",
				"desk_access": 0,
			}
		)
		role.save()


def create_moderator_role():
	if frappe.db.exists("Role", "Moderator"):
		frappe.db.set_value("Role", "Moderator", "desk_access", 0)
	else:
		role = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "Moderator",
				"home_page": "",
				"desk_access": 0,
			}
		)
		role.save()


def create_evaluator_role():
	if frappe.db.exists("Role", "Batch Evaluator"):
		frappe.db.set_value("Role", "Batch Evaluator", "desk_access", 0)
	else:
		role = frappe.new_doc("Role")
		role.update(
			{
				"role_name": "Batch Evaluator",
				"home_page": "",
				"desk_access": 0,
			}
		)
		role.save()


def create_lms_student_role():
	if frappe.db.exists("Role", "LMS Student"):
		frappe.db.set_value("Role", "LMS Student", "desk_access", 0)
	else:
		role = frappe.new_doc("Role")
		role.update(
			{
				"role_name": "LMS Student",
				"home_page": "",
				"desk_access": 0,
			}
		)
		role.save()


def set_default_certificate_print_format():
	filters = {
		"doc_type": "LMS Certificate",
		"property": "default_print_format",
	}
	if not frappe.db.exists("Property Setter", filters):
		filters.update(
			{
				"doctype_or_field": "DocType",
				"property_type": "Data",
				"value": "Certificate",
			}
		)

		doc = frappe.new_doc("Property Setter")
		doc.update(filters)
		doc.save()


def delete_custom_fields():
	fields = [
		"user_category",
		"headline",
		"college",
		"city",
		"verify_terms",
		"country",
		"preferred_location",
		"preferred_functions",
		"preferred_industries",
		"work_environment_column",
		"time",
		"role",
		"carrer_preference_details",
		"skill",
		"certification_details",
		"internship",
		"branch",
		"github",
		"medium",
		"linkedin",
		"profession",
		"open_to",
		"cover_image" "work_environment",
		"dream_companies",
		"career_preference_column",
		"attire",
		"collaboration",
		"location_preference",
		"company_type",
		"skill_details",
		"certification",
		"education",
		"work_experience",
		"education_details",
		"hide_private",
		"work_experience_details",
		"profile_complete",
	]

	for field in fields:
		frappe.db.delete("Custom Field", {"fieldname": field})


def create_batch_source():
	sources = [
		"Newsletter",
		"LinkedIn",
		"Twitter",
		"Website",
		"Friend/Colleague/Connection",
		"Google Search",
	]

	for source in sources:
		if not frappe.db.exists("LMS Source", source):
			doc = frappe.new_doc("LMS Source")
			doc.source = source
			doc.save()


def give_lms_roles_to_admin():
	roles = [
		"Course Creator",
		"Moderator",
		"Batch Evaluator",
		"LMS Trainer",
		"LMS Master Trainer",
		"LMS Manager",
		"LMS HR",
	]
	for role in roles:
		if not frappe.db.exists("Has Role", {"parent": "Administrator", "role": role}):
			doc = frappe.new_doc("Has Role")
			doc.parent = "Administrator"
			doc.parenttype = "User"
			doc.parentfield = "roles"
			doc.role = role
			doc.save()
