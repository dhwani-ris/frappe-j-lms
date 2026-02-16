import frappe
from frappe.utils import cint


@frappe.whitelist()
def get_direct_reports(manager_employee_id=None):
	"""Get direct reports for a manager using Employee.reports_to."""
	if not manager_employee_id:
		manager_employee_id = frappe.db.get_value(
			"Employee",
			{"user_id": frappe.session.user, "status": "Active"},
			"name",
		)
	if not manager_employee_id:
		return []

	reports = frappe.get_all(
		"Employee",
		filters={"reports_to": manager_employee_id, "status": "Active"},
		fields=["name", "employee_name", "user_id", "department", "designation", "image"],
	)
	return reports


@frappe.whitelist()
def get_manager_dashboard():
	"""Manager dashboard: direct reports' learning progress (read-only)."""
	frappe.only_for(["LMS Manager", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"])

	user_roles = frappe.get_roles(frappe.session.user)
	is_super = "System Manager" in user_roles or "Moderator" in user_roles or "LMS HR" in user_roles

	if is_super:
		# System Manager / Moderator / HR: show ALL active employees
		reports = frappe.get_all(
			"Employee",
			filters={"status": "Active"},
			fields=["name", "employee_name", "user_id", "department", "designation", "image"],
		)
	else:
		reports = get_direct_reports()

	for report in reports:
		if not report.user_id:
			report.enrollments = []
			report.total_courses = 0
			report.completed = 0
			report.avg_progress = 0
			continue

		enrollments = frappe.get_all(
			"LMS Enrollment",
			{"member": report.user_id},
			["course", "progress", "modified"],
		)
		for enrollment in enrollments:
			enrollment.course_title = frappe.db.get_value(
				"LMS Course", enrollment.course, "title"
			)

		report.enrollments = enrollments
		report.total_courses = len(enrollments)
		report.completed = len([e for e in enrollments if cint(e.progress) >= 100])
		report.avg_progress = (
			round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
			if enrollments
			else 0
		)

	return {
		"reports": reports,
		"summary": {
			"team_size": len(reports),
			"avg_progress": (
				round(sum(r.avg_progress for r in reports) / len(reports), 1)
				if reports
				else 0
			),
			"total_completed": sum(r.completed for r in reports),
		},
	}


@frappe.whitelist()
def get_trainer_dashboard():
	"""Trainer dashboard: batches where user is instructor + student progress."""
	frappe.only_for(["LMS Trainer", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"])

	user_roles = frappe.get_roles(frappe.session.user)
	is_super = "System Manager" in user_roles or "Moderator" in user_roles or "LMS HR" in user_roles

	if is_super:
		# System Manager / Moderator / HR: show ALL batches
		batch_names = frappe.get_all("LMS Batch", pluck="name")
	else:
		# Get batches where current user is an instructor
		instructor_batches = frappe.get_all(
			"Course Instructor",
			{"instructor": frappe.session.user},
			pluck="parent",
		)
		# Deduplicate (user can be instructor on multiple courses in same batch)
		batch_names = list(set(instructor_batches))

	batches_data = []
	total_students = 0
	total_progress = 0
	student_count_for_avg = 0
	pending_evaluations = 0

	for batch_name in batch_names:
		# Check if this is actually an LMS Batch
		if not frappe.db.exists("LMS Batch", batch_name):
			continue

		batch = frappe.db.get_value(
			"LMS Batch",
			batch_name,
			["name", "title", "start_date", "end_date"],
			as_dict=True,
		)

		students = frappe.get_all(
			"LMS Batch Enrollment",
			{"batch": batch_name},
			["member", "member_name"],
		)

		for student in students:
			enrollments = frappe.get_all(
				"LMS Enrollment",
				{"member": student.member},
				["course", "progress"],
			)
			for e in enrollments:
				e.course_title = frappe.db.get_value("LMS Course", e.course, "title")
				e.status = calculate_status(cint(e.progress))
			student.enrollments = enrollments
			student.avg_progress = (
				round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
				if enrollments
				else 0
			)
			student.total_courses = len(enrollments)
			student.status = calculate_status(student.avg_progress)
			student.user_image = frappe.db.get_value("User", student.member, "user_image")

			total_progress += student.avg_progress
			student_count_for_avg += 1

		total_students += len(students)
		batch.students = students
		batches_data.append(batch)

	# Count pending quiz/assignment submissions
	pending_evaluations = frappe.db.count(
		"LMS Quiz Submission",
		{"member": ["!=", frappe.session.user]},
	)

	return {
		"batches": batches_data,
		"summary": {
			"total_students": total_students,
			"avg_progress": (
				round(total_progress / student_count_for_avg, 1)
				if student_count_for_avg
				else 0
			),
			"pending_evaluations": pending_evaluations,
		},
	}


@frappe.whitelist()
def get_hr_employees(search="", department="", designation="", start=0, limit=20):
	"""HR: Get all employees with LMS data."""
	frappe.only_for("LMS HR")

	filters = {"status": "Active"}
	or_filters = {}

	if search:
		or_filters["employee_name"] = ["like", f"%{search}%"]
		or_filters["user_id"] = ["like", f"%{search}%"]
	if department:
		filters["department"] = department
	if designation:
		filters["designation"] = designation

	employees = frappe.get_all(
		"Employee",
		filters=filters,
		or_filters=or_filters if or_filters else None,
		fields=[
			"name", "employee_name", "user_id", "department", "designation",
			"reports_to", "image", "company",
		],
		start=cint(start),
		page_length=cint(limit),
		order_by="employee_name asc",
	)

	for emp in employees:
		if emp.user_id:
			roles = frappe.get_all("Has Role", {"parent": emp.user_id}, pluck="role")
			emp.lms_roles = [
				r for r in roles
				if r.startswith("LMS") or r in ["Course Creator", "Moderator", "Batch Evaluator"]
			]
			enrollments = frappe.get_all(
				"LMS Enrollment", {"member": emp.user_id}, ["course", "progress"]
			)
			emp.total_courses = len(enrollments)
			emp.avg_progress = (
				round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
				if enrollments
				else 0
			)
		else:
			emp.lms_roles = []
			emp.total_courses = 0
			emp.avg_progress = 0

		if emp.reports_to:
			emp.manager_name = frappe.db.get_value(
				"Employee", emp.reports_to, "employee_name"
			)
		else:
			emp.manager_name = None

	total_count = frappe.db.count("Employee", {"status": "Active"})

	return {
		"employees": employees,
		"total_count": total_count,
	}


@frappe.whitelist()
def get_hr_filters():
	"""Get filter options for HR employee list."""
	frappe.only_for("LMS HR")

	departments = frappe.get_all("Department", pluck="name", order_by="name asc")
	designations = frappe.get_all("Designation", pluck="name", order_by="name asc")
	role_profiles = frappe.get_all(
		"Role Profile",
		filters={"name": ["like", "Jamboree%"]},
		pluck="name",
		order_by="name asc",
	)

	return {
		"departments": departments,
		"designations": designations,
		"role_profiles": role_profiles,
	}


@frappe.whitelist()
def save_employee_lms_role(employee, role_profile):
	"""HR: Assign a Jamboree role profile to an employee."""
	frappe.only_for("LMS HR")

	emp = frappe.get_doc("Employee", employee)
	if not emp.user_id:
		frappe.throw("Employee has no linked User account. Please link a User first.")

	user = frappe.get_doc("User", emp.user_id)
	user.role_profile_name = role_profile
	user.save(ignore_permissions=True)
	frappe.clear_cache(user=emp.user_id)

	return {"success": True, "message": f"Role profile '{role_profile}' assigned to {emp.employee_name}"}


@frappe.whitelist()
def export_team_progress(manager_employee_id=None):
	"""Export team progress as structured data for CSV download."""
	frappe.only_for(["LMS Manager", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"])

	user_roles = frappe.get_roles(frappe.session.user)
	is_super = "System Manager" in user_roles or "Moderator" in user_roles or "LMS HR" in user_roles

	if is_super and not manager_employee_id:
		reports = frappe.get_all(
			"Employee",
			filters={"status": "Active"},
			fields=["name", "employee_name", "user_id", "department", "designation", "image"],
		)
	else:
		reports = get_direct_reports(manager_employee_id)
	rows = []

	for r in reports:
		if not r.user_id:
			continue

		enrollments = frappe.get_all(
			"LMS Enrollment", {"member": r.user_id}, ["course", "progress"]
		)

		if not enrollments:
			rows.append({
				"employee": r.employee_name,
				"department": r.department or "",
				"designation": r.designation or "",
				"course": "No courses enrolled",
				"progress": 0,
			})
			continue

		for e in enrollments:
			course_title = frappe.db.get_value("LMS Course", e.course, "title") or e.course
			rows.append({
				"employee": r.employee_name,
				"department": r.department or "",
				"designation": r.designation or "",
				"course": course_title,
				"progress": cint(e.progress),
			})

	return rows


@frappe.whitelist()
def get_employee_detail(employee):
	"""Get detailed LMS data for a single employee (for HR view)."""
	frappe.only_for("LMS HR")

	emp = frappe.db.get_value(
		"Employee",
		employee,
		["name", "employee_name", "user_id", "department", "designation",
		 "reports_to", "image", "company", "date_of_joining"],
		as_dict=True,
	)

	if not emp:
		frappe.throw("Employee not found")

	if emp.reports_to:
		emp.manager_name = frappe.db.get_value(
			"Employee", emp.reports_to, "employee_name"
		)

	if emp.user_id:
		roles = frappe.get_all("Has Role", {"parent": emp.user_id}, pluck="role")
		emp.lms_roles = [
			r for r in roles
			if r.startswith("LMS") or r in ["Course Creator", "Moderator", "Batch Evaluator"]
		]

		# Get role profile
		emp.role_profile = frappe.db.get_value("User", emp.user_id, "role_profile_name")

		# Enrollments with progress
		enrollments = frappe.get_all(
			"LMS Enrollment",
			{"member": emp.user_id},
			["name", "course", "progress", "creation", "modified"],
			order_by="creation desc",
		)
		for enrollment in enrollments:
			enrollment.course_title = frappe.db.get_value(
				"LMS Course", enrollment.course, "title"
			)
			enrollment.status = (
				"Completed" if cint(enrollment.progress) >= 100
				else ("In Progress" if cint(enrollment.progress) > 0 else "Not Started")
			)

		emp.enrollments = enrollments

		# Quiz submissions
		emp.quiz_submissions = frappe.get_all(
			"LMS Quiz Submission",
			{"member": emp.user_id},
			["name", "quiz", "score", "creation"],
			order_by="creation desc",
			limit=10,
		)

		# Certificates
		emp.certificates = frappe.get_all(
			"LMS Certificate",
			{"member": emp.user_id},
			["name", "course", "creation"],
			order_by="creation desc",
		)
	else:
		emp.lms_roles = []
		emp.role_profile = None
		emp.enrollments = []
		emp.quiz_submissions = []
		emp.certificates = []

	return emp


@frappe.whitelist()
def update_employee_manager(employee, reports_to):
	"""HR: Update the manager (reports_to) of an employee."""
	frappe.only_for("LMS HR")

	emp = frappe.get_doc("Employee", employee)
	if reports_to and reports_to == employee:
		frappe.throw("An employee cannot report to themselves")

	emp.reports_to = reports_to or None
	emp.save(ignore_permissions=True)
	frappe.db.commit()

	manager_name = None
	if reports_to:
		manager_name = frappe.db.get_value("Employee", reports_to, "employee_name")

	return {
		"success": True,
		"message": f"Manager updated for {emp.employee_name}",
		"manager_name": manager_name,
	}


@frappe.whitelist()
def create_employee(employee_name, gender=None, date_of_birth=None, user_email=None, department=None, designation=None, reports_to=None, company=None, date_of_joining=None, role_profile=None, create_user=0):
	"""HR: Create a new employee and optionally create a User account + assign role profile."""
	frappe.only_for("LMS HR")

	if not employee_name:
		frappe.throw("Employee name is required")

	create_user = cint(create_user)

	# Get default company
	if not company:
		company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		companies = frappe.get_all("Company", limit=1, pluck="name")
		company = companies[0] if companies else None
	if not company:
		frappe.throw("No company found. Please specify a company.")

	# Handle user creation/linking
	actual_user_id = None
	user_created = False
	if user_email:
		if frappe.db.exists("User", user_email):
			actual_user_id = user_email
		elif create_user:
			# Create new User account
			name_parts = employee_name.strip().split(" ", 1)
			first_name = name_parts[0]
			last_name = name_parts[1] if len(name_parts) > 1 else ""

			new_user = frappe.new_doc("User")
			new_user.email = user_email
			new_user.first_name = first_name
			new_user.last_name = last_name
			new_user.enabled = 1
			new_user.send_welcome_email = 0
			new_user.new_password = frappe.generate_hash(length=12)
			new_user.save(ignore_permissions=True)
			actual_user_id = user_email
			user_created = True
		else:
			frappe.throw(f"User {user_email} does not exist. Check 'Create user account' to create one.")

	emp = frappe.new_doc("Employee")
	emp.employee_name = employee_name
	name_parts = employee_name.strip().split(" ", 1)
	emp.first_name = name_parts[0]
	if len(name_parts) > 1:
		emp.last_name = name_parts[1]
	emp.company = company
	emp.status = "Active"
	emp.gender = gender or "Male"
	emp.date_of_birth = date_of_birth or "1990-01-01"

	if actual_user_id:
		emp.user_id = actual_user_id

	if department:
		emp.department = department
	if designation:
		emp.designation = designation
	if reports_to:
		emp.reports_to = reports_to
	if date_of_joining:
		emp.date_of_joining = date_of_joining
	else:
		from frappe.utils import today
		emp.date_of_joining = today()

	emp.save(ignore_permissions=True)
	frappe.db.commit()

	# Assign role profile if specified and user exists
	if role_profile and actual_user_id and frappe.db.exists("Role Profile", role_profile):
		from lms.lms.custom.jamboree_setup import assign_role_profile_to_user
		assign_role_profile_to_user(actual_user_id, role_profile)

	msg = f"Employee '{employee_name}' created successfully"
	if user_created:
		msg += f" with new user account ({user_email})"

	return {
		"success": True,
		"employee": emp.name,
		"user_created": user_created,
		"message": msg,
	}


@frappe.whitelist()
def get_employee_options():
	"""Get all active employees for dropdowns (manager selection)."""
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name"],
		order_by="employee_name asc",
		limit_page_length=0,
	)
	return employees


def calculate_status(avg_progress):
	"""Calculate student status based on progress."""
	if avg_progress == 0:
		return "Not Started"
	if avg_progress >= 100:
		return "Completed"
	if avg_progress >= 50:
		return "On Track"
	return "Behind"
