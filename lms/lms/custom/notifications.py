import frappe
from frappe.utils import cint


def check_student_progress_alerts():
	"""Daily scheduled task: notify trainers/managers about students who are behind."""
	# Get all active enrollments with low progress
	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"progress": ["<", 50], "progress": [">", 0]},
		fields=["member", "course", "progress"],
	)

	for enrollment in enrollments:
		# Find the student's manager via Employee
		employee = frappe.db.get_value(
			"Employee",
			{"user_id": enrollment.member, "status": "Active"},
			["name", "reports_to", "employee_name"],
			as_dict=True,
		)

		if not employee or not employee.reports_to:
			continue

		manager_user = frappe.db.get_value(
			"Employee", employee.reports_to, "user_id"
		)

		if not manager_user:
			continue

		course_title = frappe.db.get_value("LMS Course", enrollment.course, "title")

		# Send notification to manager
		notification = frappe.new_doc("Notification Log")
		notification.for_user = manager_user
		notification.from_user = frappe.session.user
		notification.type = "Alert"
		notification.subject = (
			f"{employee.employee_name} is behind on '{course_title}' "
			f"(Progress: {cint(enrollment.progress)}%)"
		)
		notification.document_type = "LMS Enrollment"
		notification.document_name = enrollment.member
		notification.save(ignore_permissions=True)


def notify_on_quiz_submission(doc, method):
	"""Notify trainer when a student submits a quiz."""
	# Find instructors of the course
	course = frappe.db.get_value("LMS Quiz", doc.quiz, "course")
	if not course:
		return

	instructors = frappe.get_all(
		"Course Instructor",
		{"parent": course},
		pluck="instructor",
	)

	student_name = frappe.db.get_value("User", doc.member, "full_name") or doc.member
	quiz_title = frappe.db.get_value("LMS Quiz", doc.quiz, "title") or doc.quiz

	for instructor in instructors:
		notification = frappe.new_doc("Notification Log")
		notification.for_user = instructor
		notification.from_user = doc.member
		notification.type = "Alert"
		notification.subject = f"{student_name} submitted quiz '{quiz_title}'"
		notification.document_type = "LMS Quiz Submission"
		notification.document_name = doc.name
		notification.save(ignore_permissions=True)


def notify_on_course_completion(doc, method):
	"""Notify trainer and manager when a student completes a course."""
	if cint(doc.progress) < 100:
		return

	# Check if we already sent a completion notification
	existing = frappe.db.exists(
		"Notification Log",
		{
			"document_type": "LMS Enrollment",
			"document_name": doc.name,
			"subject": ["like", "%completed the course%"],
		},
	)
	if existing:
		return

	student_name = frappe.db.get_value("User", doc.member, "full_name") or doc.member
	course_title = frappe.db.get_value("LMS Course", doc.course, "title") or doc.course

	# Notify instructors
	instructors = frappe.get_all(
		"Course Instructor",
		{"parent": doc.course},
		pluck="instructor",
	)

	for instructor in instructors:
		notification = frappe.new_doc("Notification Log")
		notification.for_user = instructor
		notification.from_user = doc.member
		notification.type = "Alert"
		notification.subject = f"{student_name} completed the course '{course_title}'"
		notification.document_type = "LMS Enrollment"
		notification.document_name = doc.name
		notification.save(ignore_permissions=True)

	# Notify manager via Employee hierarchy
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": doc.member, "status": "Active"},
		["reports_to"],
		as_dict=True,
	)

	if employee and employee.reports_to:
		manager_user = frappe.db.get_value(
			"Employee", employee.reports_to, "user_id"
		)
		if manager_user:
			notification = frappe.new_doc("Notification Log")
			notification.for_user = manager_user
			notification.from_user = doc.member
			notification.type = "Alert"
			notification.subject = f"{student_name} completed the course '{course_title}'"
			notification.document_type = "LMS Enrollment"
			notification.document_name = doc.name
			notification.save(ignore_permissions=True)
