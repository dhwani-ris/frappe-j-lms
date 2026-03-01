import frappe
from frappe.utils import today, add_months


@frappe.whitelist()
def assign_course_to_student(student_email, course, assigned_by=None, trainers=None, start_date=None, end_date=None):
	"""Assign a course to a student via the auto-batch (micro-batch) pattern."""
	frappe.only_for(["LMS Master Trainer", "LMS HR", "Moderator"])

	if not assigned_by:
		assigned_by = frappe.session.user

	# Parse trainers from JSON string if needed (frappe.whitelist sends lists as JSON strings)
	if isinstance(trainers, str):
		import json
		trainers = json.loads(trainers) if trainers else []
	elif not trainers:
		trainers = []

	# If no trainers specified, use the assigning user
	if not trainers:
		trainers = [assigned_by]

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

	# Add all selected trainers as instructors
	for trainer_email in trainers:
		batch.append("instructors", {"instructor": trainer_email})

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
def unassign_course_from_student(student_email, course):
	"""Remove course assignment from a student by deleting the auto-batch and enrollments."""
	frappe.only_for(["LMS Master Trainer", "LMS HR", "Moderator"])

	if not frappe.db.exists("User", student_email):
		frappe.throw(f"User {student_email} does not exist")

	if not frappe.db.exists("LMS Course", course):
		frappe.throw(f"Course {course} does not exist")

	# Find the auto-batch for this student+course combination
	course_title = frappe.db.get_value("LMS Course", course, "title")
	student_name = frappe.db.get_value("User", student_email, "full_name") or student_email
	batch_title_pattern = f"{student_name} - {course_title}"

	# Get the batch with this exact title
	batch = frappe.db.get_value("LMS Batch", {"title": batch_title_pattern}, "name")

	if not batch:
		frappe.throw(f"No auto-batch found for {student_name} - {course_title}")

	# Delete linked discussion topics first (to avoid foreign key constraint)
	discussion_topics = frappe.get_all(
		"Discussion Topic",
		{"reference_doctype": "LMS Batch", "reference_docname": batch},
		pluck="name"
	)
	for topic in discussion_topics:
		frappe.delete_doc("Discussion Topic", topic, ignore_permissions=True, force=True)

	# Delete course enrollment
	course_enrollment = frappe.db.get_value(
		"LMS Enrollment", {"member": student_email, "course": course}, "name"
	)
	if course_enrollment:
		frappe.delete_doc("LMS Enrollment", course_enrollment, ignore_permissions=True, force=True)

	# Delete batch enrollment
	batch_enrollment = frappe.db.get_value(
		"LMS Batch Enrollment", {"member": student_email, "batch": batch}, "name"
	)
	if batch_enrollment:
		frappe.delete_doc("LMS Batch Enrollment", batch_enrollment, ignore_permissions=True, force=True)

	# Delete the auto-batch itself
	frappe.delete_doc("LMS Batch", batch, ignore_permissions=True, force=True)

	return {
		"message": f"Course '{course_title}' unassigned from {student_name}",
		"batch_deleted": batch,
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
	frappe.only_for(["LMS Master Trainer", "LMS HR", "Moderator"])

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


@frappe.whitelist()
def get_all_assignments():
	"""Get all course assignments with complete details including trainers."""
	frappe.only_for(["LMS Master Trainer", "LMS HR", "Moderator", "LMS Trainer"])

	# Get all enrollments
	enrollments = frappe.get_all(
		"LMS Enrollment",
		fields=["name", "member", "course", "progress", "creation"],
		order_by="creation desc",
	)

	assignments = []
	for enrollment in enrollments:
		# Get basic info
		course_title = frappe.db.get_value("LMS Course", enrollment.course, "title")
		student_name = frappe.db.get_value("User", enrollment.member, "full_name") or enrollment.member

		# Find the auto-batch for this student+course combination
		batch_title_pattern = f"{student_name} - {course_title}"
		batch = frappe.db.get_value(
			"LMS Batch",
			{"title": batch_title_pattern},
			["name", "start_date", "end_date"],
			as_dict=True
		)

		if not batch:
			# Skip if no batch found (might be manually enrolled)
			continue

		# Get trainers/instructors for this batch
		instructors = frappe.get_all(
			"Course Instructor",
			{"parent": batch.name, "parenttype": "LMS Batch"},
			["instructor"],
		)

		trainers = [inst.instructor for inst in instructors]
		trainers_names = ", ".join([
			frappe.db.get_value("User", trainer, "full_name") or trainer
			for trainer in trainers
		]) if trainers else None

		assignments.append({
			"name": enrollment.name,
			"member": enrollment.member,
			"student_name": student_name,
			"course": enrollment.course,
			"course_title": course_title,
			"batch": batch.name,
			"trainers": trainers,
			"trainers_names": trainers_names,
			"start_date": batch.start_date,
			"end_date": batch.end_date,
			"progress": enrollment.progress or 0,
			"creation": enrollment.creation,
		})

	return assignments
