import frappe


def delete_all_lms_custom_docperms():
	"""Delete all existing Custom DocPerms for LMS doctypes to start fresh."""
	lms_doctypes = [
		"LMS Course",
		"LMS Enrollment",
		"LMS Batch",
		"LMS Batch Enrollment",
		"Course Lesson",
		"Course Chapter",
		"LMS Quiz",
		"LMS Quiz Submission",
		"LMS Assignment",
		"LMS Assignment Submission",
		"LMS Certificate",
		"LMS Certificate Request",
		"LMS Category",
		"LMS Course Progress",
	]

	for doctype in lms_doctypes:
		# Delete all Custom DocPerms for this doctype
		frappe.db.delete("Custom DocPerm", {"parent": doctype})
		print(f"Deleted all Custom DocPerms for {doctype}")

	frappe.db.commit()
	print("\n✓ All LMS Custom DocPerms deleted successfully!")


def recreate_all_lms_permissions():
	"""Recreate all LMS permissions with complete permission sets."""

	# Complete permission definitions with ALL fields
	all_permissions = [
		# ============ LMS Course ============
		{"parent": "LMS Course", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Course", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Course", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Course", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Enrollment ============
		{"parent": "LMS Enrollment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Enrollment", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Enrollment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Enrollment", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Enrollment", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Enrollment", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Enrollment", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Batch ============
		{"parent": "LMS Batch", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Batch", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Batch Enrollment ============
		{"parent": "LMS Batch Enrollment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch Enrollment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch Enrollment", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch Enrollment", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Batch Enrollment", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Batch Enrollment", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch Enrollment", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Batch Enrollment", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ Course Lesson ============
		{"parent": "Course Lesson", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Lesson", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "Course Lesson", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Lesson", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Lesson", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "Course Lesson", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "Course Lesson", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ Course Chapter ============
		{"parent": "Course Chapter", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Chapter", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "Course Chapter", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Chapter", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Chapter", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "Course Chapter", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "Course Chapter", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "Course Chapter", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Quiz ============
		{"parent": "LMS Quiz", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Quiz", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Quiz", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Quiz", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Quiz", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Quiz Submission ============
		{"parent": "LMS Quiz Submission", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Quiz Submission", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz Submission", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Quiz Submission", "role": "LMS Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz Submission", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Quiz Submission", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Assignment ============
		{"parent": "LMS Assignment", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "role": "LMS Student", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Assignment Submission ============
		{"parent": "LMS Assignment Submission", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment Submission", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Assignment Submission", "role": "LMS Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment Submission", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Assignment Submission", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Certificate ============
		{"parent": "LMS Certificate", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "role": "LMS Student", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Certificate", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "role": "Course Creator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Certificate", "role": "LMS Trainer", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Certificate", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Certificate Request ============
		{"parent": "LMS Certificate Request", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate Request", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate Request", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Certificate Request", "role": "Batch Evaluator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Certificate Request", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Certificate Request", "role": "LMS Trainer", "read": 1, "write": 1, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Certificate Request", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Category ============
		{"parent": "LMS Category", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Category", "role": "Moderator", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Category", "role": "Course Creator", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Category", "role": "Batch Evaluator", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Category", "role": "LMS Master Trainer", "read": 1, "write": 1, "create": 1, "delete": 0, "export": 1, "import": 1},
		{"parent": "LMS Category", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},

		# ============ LMS Course Progress ============
		{"parent": "LMS Course Progress", "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
		{"parent": "LMS Course Progress", "role": "LMS Student", "read": 1, "write": 0, "create": 1, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Course Progress", "role": "LMS Manager", "read": 1, "write": 0, "create": 0, "delete": 0, "export": 0, "import": 0},
		{"parent": "LMS Course Progress", "role": "LMS HR", "read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "import": 1},
	]

	# Create all permissions
	for perm in all_permissions:
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
		print(f"Created: {perm['parent']} - {perm['role']}")

	frappe.db.commit()
	print("\n✓ All LMS permissions recreated successfully!")


def fix_lms_permissions():
	"""Main function to fix all LMS permissions."""
	print("=" * 80)
	print("FIXING LMS PERMISSIONS")
	print("=" * 80)
	print("\nStep 1: Deleting all existing Custom DocPerms for LMS doctypes...")
	delete_all_lms_custom_docperms()

	print("\nStep 2: Recreating all permissions with complete permission sets...")
	recreate_all_lms_permissions()

	print("\n" + "=" * 80)
	print("✓ PERMISSION FIX COMPLETE!")
	print("=" * 80)
	print("\nPlease refresh the Permission Manager page to see the updated permissions.")
