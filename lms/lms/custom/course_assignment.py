import frappe
from frappe.utils import today, add_months


@frappe.whitelist()
def assign_course_to_student(student_email, course, assigned_by=None, start_date=None, end_date=None):
	"""Assign a course to a student via the auto-batch (micro-batch) pattern."""
	frappe.only_for(["LMS Trainer", "LMS Master Trainer", "LMS HR"])

	if not assigned_by:
		assigned_by = frappe.session.user

	if not frappe.db.exists("User", student_email):
		frappe.throw(f"User {student_email} does not exist")

	if not frappe.db.exists("LMS Course", course):
		frappe.throw(f"Course {course} does not exist")

	# Check if already enrolled
	existing = frappe.db.exists(
		"LMS Enrollment", {"member": student_email, "course": course}
	)
	if existing:
		frappe.throw(f"Student is already enrolled in this course")

	course_title = frappe.db.get_value("LMS Course", course, "title")
	student_name = frappe.db.get_value("User", student_email, "full_name") or student_email

	# Create micro-batch (1 student per batch)
	batch = frappe.new_doc("LMS Batch")
	batch.title = f"{student_name} - {course_title}"
	batch.description = f"Auto-assigned: {course_title} for {student_name}"
	batch.batch_details = f"<p>Auto-assigned course for {student_name}</p>"
	batch.start_date = start_date or today()
	batch.end_date = end_date or add_months(batch.start_date, 3)
	batch.start_time = "09:00:00"
	batch.end_time = "18:00:00"
	batch.timezone = frappe.db.get_single_value("System Settings", "time_zone") or "Asia/Kolkata"
	batch.published = 1
	batch.append("courses", {"course": course})
	batch.append("instructors", {"instructor": assigned_by})
	batch.save(ignore_permissions=True)

	# Create course enrollment first (so batch enrollment validation skips auto-creation)
	course_enrollment = frappe.new_doc("LMS Enrollment")
	course_enrollment.member = student_email
	course_enrollment.course = course
	course_enrollment.save(ignore_permissions=True)

	# Create batch enrollment
	batch_enrollment = frappe.new_doc("LMS Batch Enrollment")
	batch_enrollment.member = student_email
	batch_enrollment.batch = batch.name
	batch_enrollment.save(ignore_permissions=True)

	enrollment_name = course_enrollment.name

	return {
		"batch": batch.name,
		"enrollment": enrollment_name,
		"message": f"Course '{course_title}' assigned to {student_name}",
	}


@frappe.whitelist()
def get_student_assignments(student_email=None):
	"""Get all course assignments for a student."""
	if not student_email:
		student_email = frappe.session.user

	enrollments = frappe.get_all(
		"LMS Enrollment",
		{"member": student_email},
		["name", "course", "progress", "modified", "creation"],
		order_by="creation desc",
	)

	for e in enrollments:
		e.course_title = frappe.db.get_value("LMS Course", e.course, "title")
		progress = e.progress or 0
		if progress >= 100:
			e.status = "Completed"
		elif progress > 0:
			e.status = "In Progress"
		else:
			e.status = "Not Started"

	return enrollments


@frappe.whitelist()
def get_recent_assignments(limit=10):
	"""Get recently assigned courses (for the assign course page)."""
	frappe.only_for(["LMS Trainer", "LMS Master Trainer", "LMS HR"])

	enrollments = frappe.get_all(
		"LMS Enrollment",
		fields=["name", "member", "course", "progress", "creation"],
		order_by="creation desc",
		limit=limit,
	)

	for e in enrollments:
		e.course_title = frappe.db.get_value("LMS Course", e.course, "title")
		e.student_name = frappe.db.get_value("User", e.member, "full_name") or e.member

	return enrollments
