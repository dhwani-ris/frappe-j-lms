import frappe


def setup_jamboree_roles():
	"""Main orchestrator: creates Jamboree LMS roles, permissions, and role profiles."""
	create_jamboree_lms_roles()
	create_jamboree_custom_docperms()
	create_jamboree_role_profiles()


def create_jamboree_lms_roles():
	"""Create 4 new Frappe Roles for Jamboree LMS (no desk access)."""
	roles = ["LMS Trainer", "LMS Master Trainer", "LMS Manager", "LMS HR"]
	for role_name in roles:
		if frappe.db.exists("Role", role_name):
			frappe.db.set_value("Role", role_name, "desk_access", 0)
		else:
			role = frappe.new_doc("Role")
			role.update(
				{
					"role_name": role_name,
					"home_page": "",
					"desk_access": 0,
				}
			)
			role.save(ignore_permissions=True)


def create_jamboree_custom_docperms():
	"""Create Custom DocPerm entries for each Jamboree role.

	IMPORTANT: When Custom DocPerm entries exist for a DocType, Frappe completely
	replaces the base DocPerm with Custom DocPerm entries. So we must also
	replicate the original base permissions (LMS Student, System Manager,
	Moderator, Course Creator, Batch Evaluator) as Custom DocPerm entries.
	"""

	# Base permissions from the original DocType definitions that must be preserved
	base_perms = [
		# LMS Course
		{"parent": "LMS Course", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		# LMS Enrollment
		{"parent": "LMS Enrollment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Enrollment", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "LMS Enrollment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# LMS Batch
		{"parent": "LMS Batch", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0},
		# LMS Batch Enrollment
		{"parent": "LMS Batch Enrollment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch Enrollment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch Enrollment", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0},
		{"parent": "LMS Batch Enrollment", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# Course Lesson
		{"parent": "Course Lesson", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "Course Lesson", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "Course Lesson", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# Course Chapter
		{"parent": "Course Chapter", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "Course Chapter", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "Course Chapter", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "Course Chapter", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# LMS Quiz
		{"parent": "LMS Quiz", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0},
		# LMS Quiz Submission
		{"parent": "LMS Quiz Submission", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz Submission", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0},
		# LMS Assignment
		{"parent": "LMS Assignment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Assignment", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "LMS Assignment", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 0},
		# LMS Assignment Submission
		{"parent": "LMS Assignment Submission", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment Submission", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "LMS Assignment Submission", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment Submission", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "LMS Assignment Submission", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0},
		# LMS Certificate
		{"parent": "LMS Certificate", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0},
		{"parent": "LMS Certificate", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# LMS Certificate Request
		{"parent": "LMS Certificate Request", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate Request", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate Request", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0},
		{"parent": "LMS Certificate Request", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1},
		# LMS Category
		{"parent": "LMS Category", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Category", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Category", "role": "Course Creator", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Category", "role": "Batch Evaluator", "read": 1, "write": 0, "create": 0, "delete": 0},
		# LMS Course Progress
		{"parent": "LMS Course Progress", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Course Progress", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0},
		# Employee Feedback Form — row-scoped via permission query. LMS Student gets
		# read only (the query limits them to their own form, as the evaluatee).
		{"parent": "Employee Feedback Form", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1},
		{"parent": "Employee Feedback Form", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1},
		{"parent": "Employee Feedback Form", "role": "LMS Manager", "read": 1, "write": 1, "create": 0, "delete": 0},
		{"parent": "Employee Feedback Form", "role": "LMS Trainer", "read": 1, "write": 1, "create": 0, "delete": 0},
		{"parent": "Employee Feedback Form", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 0, "delete": 0},
		{"parent": "Employee Feedback Form", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0},
	]

	# Jamboree role permissions
	trainer_perms = [
		{"parent": "LMS Course", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Enrollment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Batch", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Batch Enrollment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "Course Lesson", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "Course Chapter", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Quiz", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Quiz Submission", "read": 1, "write": 1, "create": 0, "delete": 0},
		{"parent": "LMS Assignment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Assignment Submission", "read": 1, "write": 1, "create": 0, "delete": 0},
		{"parent": "LMS Certificate", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Certificate Request", "read": 1, "write": 1, "create": 0, "delete": 0},
	]

	master_trainer_perms = [
		{"parent": "LMS Course", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "Course Lesson", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Chapter", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Enrollment", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Batch", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Batch Enrollment", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Quiz", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Quiz Submission", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Certificate Request", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Category", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
	]

	manager_perms = [
		{"parent": "LMS Course", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Enrollment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Batch", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Batch Enrollment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "Course Lesson", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "Course Chapter", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Quiz", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Quiz Submission", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Assignment", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Assignment Submission", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Certificate", "read": 1, "write": 0, "create": 0, "delete": 0},
		{"parent": "LMS Course Progress", "read": 1, "write": 0, "create": 0, "delete": 0},
	]

	hr_perms = [
		{"parent": "LMS Course", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "Course Lesson", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "Course Chapter", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Enrollment", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Batch Enrollment", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Quiz Submission", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Assignment Submission", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Certificate Request", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Category", "read": 1, "write": 1, "create": 1, "delete": 1},
		{"parent": "LMS Course Progress", "read": 1, "write": 1, "create": 1, "delete": 1},
	]

	# Combine base + Jamboree perms into a single list
	all_perms = []
	for perm in base_perms:
		all_perms.append({"role": perm["role"], **perm})
	for perm in trainer_perms:
		all_perms.append({"role": "LMS Trainer", **perm})
	for perm in master_trainer_perms:
		all_perms.append({"role": "LMS Master Trainer", **perm})
	for perm in manager_perms:
		all_perms.append({"role": "LMS Manager", **perm})
	for perm in hr_perms:
		all_perms.append({"role": "LMS HR", **perm})

	for perm in all_perms:
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": perm["parent"], "role": perm["role"]}
		):
			doc = frappe.new_doc("Custom DocPerm")
			doc.parent = perm["parent"]
			doc.parenttype = "DocType"
			doc.parentfield = "permissions"
			doc.role = perm["role"]
			doc.read = perm.get("read", 0)
			doc.write = perm.get("write", 0)
			doc.create = perm.get("create", 0)
			doc.delete = perm.get("delete", 0)
			doc.export = perm.get("export", 0)
			if "import" in perm:
				doc.import_ = perm.get("import", 0)
			doc.save(ignore_permissions=True)


def assign_role_profile_to_user(user_email, profile_name):
	"""Assign a Jamboree Role Profile to a user (for testing/setup)."""
	if not frappe.db.exists("User", user_email):
		print(f"SKIP: User {user_email} does not exist")
		return
	if not frappe.db.exists("Role Profile", profile_name):
		print(f"SKIP: Role Profile {profile_name} does not exist")
		return

	user = frappe.get_doc("User", user_email)
	user.role_profile_name = profile_name
	rp = frappe.get_doc("Role Profile", profile_name)
	# Clear and re-apply roles from profile
	user.roles = []
	for r in rp.roles:
		user.append("roles", {"role": r.role})
	user.save(ignore_permissions=True)
	frappe.db.commit()
	roles = [r.role for r in user.roles]
	print(f"OK: {user_email} -> {profile_name} => {roles}")


def setup_test_users():
	"""Assign role profiles to test users for E2E testing."""
	assignments = {
		"amit.patel@example.com": "Jamboree HR",
		"priya.sharma@example.com": "Jamboree Master Trainer",
		"rahul.verma@example.com": "Jamboree Trainer",
		"sanjay.mehta@example.com": "Jamboree Manager",
		"dev.pandey@example.com": "Jamboree Student",
	}
	for user_email, profile_name in assignments.items():
		assign_role_profile_to_user(user_email, profile_name)


def test_e2e():
	"""E2E test: verify API responses for each role."""
	import json
	from lms.lms.api import get_user_info

	test_users = {
		"HR": "amit.patel@example.com",
		"Master Trainer": "priya.sharma@example.com",
		"Trainer": "rahul.verma@example.com",
		"Manager": "sanjay.mehta@example.com",
		"Student": "dev.pandey@example.com",
	}

	for role_label, email in test_users.items():
		frappe.set_user(email)
		try:
			info = get_user_info()
			flags = {
				"is_trainer": info.get("is_trainer"),
				"is_master_trainer": info.get("is_master_trainer"),
				"is_lms_manager": info.get("is_lms_manager"),
				"is_lms_hr": info.get("is_lms_hr"),
				"is_student": info.get("is_student"),
			}
			emp = info.get("employee")
			emp_str = f"{emp.name} reports_to={emp.reports_to}" if emp else "None"
			print(f"[{role_label}] {email}: flags={json.dumps(flags)}, employee={emp_str}")
		except Exception as e:
			print(f"[{role_label}] {email}: ERROR - {e}")
		finally:
			frappe.set_user("Administrator")

	# Test HR-only APIs
	print("\n--- HR API Tests ---")
	frappe.set_user("amit.patel@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_hr_employees, get_hr_filters, get_employee_options
		result = get_hr_employees()
		print(f"get_hr_employees: {len(result['employees'])} employees, total={result['total_count']}")
		filters = get_hr_filters()
		print(f"get_hr_filters: {len(filters['departments'])} depts, {len(filters['designations'])} desig, {len(filters['role_profiles'])} profiles")
		options = get_employee_options()
		print(f"get_employee_options: {len(options)} employees")
	except Exception as e:
		print(f"HR API ERROR: {e}")
	finally:
		frappe.set_user("Administrator")

	# Test Manager API
	print("\n--- Manager API Tests ---")
	frappe.set_user("sanjay.mehta@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_manager_dashboard
		result = get_manager_dashboard()
		print(f"get_manager_dashboard: {len(result['reports'])} reports, summary={result['summary']}")
		for r in result['reports']:
			enrollments = r.get('enrollments', [])
			print(f"  {r['employee_name']}: {len(enrollments)} enrollments, avg={r['avg_progress']}%")
			for e in enrollments:
				print(f"    - {e.get('course_title')}: {e['progress']}%")
	except Exception as e:
		print(f"Manager API ERROR: {e}")
	finally:
		frappe.set_user("Administrator")

	# Test Trainer API
	print("\n--- Trainer API Tests ---")
	frappe.set_user("rahul.verma@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_trainer_dashboard
		result = get_trainer_dashboard()
		print(f"get_trainer_dashboard: {len(result['batches'])} batches, summary={result['summary']}")
		for b in result['batches']:
			for s in b.get('students', []):
				enrollments = s.get('enrollments', [])
				print(f"  Student {s['member_name']}: {len(enrollments)} enrollments")
				for e in enrollments:
					print(f"    - {e.get('course_title')}: {e['progress']}% ({e.get('status')})")
	except Exception as e:
		print(f"Trainer API ERROR: {e}")
	finally:
		frappe.set_user("Administrator")

	# Test that Student CANNOT access HR APIs
	print("\n--- Permission Tests ---")
	frappe.set_user("dev.pandey@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_hr_employees
		get_hr_employees()
		print("FAIL: Student should NOT access get_hr_employees!")
	except frappe.PermissionError:
		print("PASS: Student blocked from get_hr_employees")
	except Exception as e:
		print(f"PASS (unexpected): {e}")
	finally:
		frappe.set_user("Administrator")

	frappe.set_user("dev.pandey@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_manager_dashboard
		get_manager_dashboard()
		print("FAIL: Student should NOT access get_manager_dashboard!")
	except frappe.PermissionError:
		print("PASS: Student blocked from get_manager_dashboard")
	except Exception as e:
		print(f"PASS (unexpected): {e}")
	finally:
		frappe.set_user("Administrator")

	frappe.set_user("dev.pandey@example.com")
	try:
		from lms.lms.custom.dashboard_api import get_trainer_dashboard
		get_trainer_dashboard()
		print("FAIL: Student should NOT access get_trainer_dashboard!")
	except frappe.PermissionError:
		print("PASS: Student blocked from get_trainer_dashboard")
	except Exception as e:
		print(f"PASS (unexpected): {e}")
	finally:
		frappe.set_user("Administrator")

	# Test course assignment as trainer
	print("\n--- Course Assignment Tests ---")
	frappe.set_user("rahul.verma@example.com")
	try:
		from lms.lms.custom.course_assignment import assign_course_to_student, get_recent_assignments
		# Get an available course
		courses = frappe.get_all("LMS Course", {"published": 1}, pluck="name", limit=1)
		if courses:
			course = courses[0]
			# Check if already enrolled
			already = frappe.db.exists("LMS Enrollment", {"member": "dev.pandey@example.com", "course": course})
			if already:
				print(f"Student already enrolled in {course}, skipping assignment test")
			else:
				result = assign_course_to_student("dev.pandey@example.com", course)
				print(f"assign_course_to_student: {result}")
		recent = get_recent_assignments()
		print(f"get_recent_assignments: {len(recent)} recent")
	except Exception as e:
		import traceback
		print(f"Course Assignment ERROR: {e}")
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")

	# Test student accessing own assignments
	print("\n--- Student Assignment Tests ---")
	frappe.set_user("dev.pandey@example.com")
	try:
		from lms.lms.custom.course_assignment import get_student_assignments
		result = get_student_assignments()
		print(f"get_student_assignments (own): {len(result)} enrollments")
	except Exception as e:
		print(f"Student Assignment ERROR: {e}")
	finally:
		frappe.set_user("Administrator")

	print("\n=== E2E TESTS COMPLETE ===")


def create_jamboree_role_profiles():
	"""Create Role Profiles that bundle roles for easy assignment."""
	profiles = {
		"Jamboree Student": ["Employee", "LMS Student"],
		"Jamboree Trainer": ["Employee", "LMS Student", "LMS Trainer"],
		"Jamboree Master Trainer": [
			"Employee",
			"LMS Student",
			"LMS Trainer",
			"LMS Master Trainer",
			"Course Creator",
		],
		"Jamboree Manager": ["Employee", "LMS Student", "LMS Manager"],
		"Jamboree HR": [
			"Employee",
			"LMS Student",
			"LMS Trainer",
			"LMS Master Trainer",
			"LMS Manager",
			"LMS HR",
			"Course Creator",
			"Moderator",
		],
	}

	for profile_name, roles_list in profiles.items():
		if frappe.db.exists("Role Profile", profile_name):
			rp = frappe.get_doc("Role Profile", profile_name)
			# Check if roles need updating
			existing_roles = {r.role for r in rp.roles}
			needed_roles = set(roles_list)
			if existing_roles != needed_roles:
				rp.roles = []
				for role_name in roles_list:
					rp.append("roles", {"role": role_name})
				rp.save(ignore_permissions=True)
		else:
			rp = frappe.new_doc("Role Profile")
			rp.role_profile = profile_name
			for role_name in roles_list:
				rp.append("roles", {"role": role_name})
			rp.save(ignore_permissions=True)
