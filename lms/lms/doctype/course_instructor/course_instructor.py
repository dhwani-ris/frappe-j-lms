# Copyright (c) 2022, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourseInstructor(Document):
	pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def instructor_query(doctype, txt, searchfield, start, page_len, filters):
	"""Query to fetch only users with LMS Trainer role"""
	return frappe.db.sql(
		"""
		SELECT DISTINCT u.name, u.full_name
		FROM `tabUser` u
		INNER JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role = 'LMS Trainer'
			AND u.enabled = 1
			AND u.name LIKE %(txt)s
		ORDER BY u.full_name
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"txt": "%" + txt + "%",
			"start": start,
			"page_len": page_len
		}
	)
