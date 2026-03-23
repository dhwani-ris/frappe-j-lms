import frappe


def debug_pending_evaluations():
	"""Debug why pending evaluations is showing 6 instead of 0."""

	print("=" * 80)
	print("DEBUGGING PENDING EVALUATIONS")
	print("=" * 80)

	# Check students in specific batches
	print('\nShukla JII - Sequential batch:')
	batch_members_1 = frappe.get_all('LMS Batch Enrollment',
		{'batch': 'shukla-jii-sequential'},
		['member', 'member_name'])
	for m in batch_members_1:
		print(f'  - {m.member_name} ({m.member})')

	print('\nPuja - LMS testing batch:')
	batch_members_2 = frappe.get_all('LMS Batch Enrollment',
		{'batch': 'puja-lms-testing'},
		['member', 'member_name'])
	for m in batch_members_2:
		print(f'  - {m.member_name} ({m.member})')

	# Get all students from both batches
	all_members = frappe.get_all('LMS Batch Enrollment',
		{'batch': ['in', ['shukla-jii-sequential', 'puja-lms-testing']]},
		pluck='member')
	print(f'\nTotal unique members in batches: {len(set(all_members))}')
	print(f'Members: {list(set(all_members))}')

	# Check quiz submissions for these members
	if all_members:
		student_list = list(set(all_members))

		quiz_subs = frappe.get_all(
			"LMS Quiz Submission",
			{"member": ["in", student_list]},
			["name", "member", "quiz", "creation"],
		)
		print(f"\nQuiz Submissions from these students: {len(quiz_subs)}")
		for sub in quiz_subs:
			member_name = frappe.db.get_value("User", sub.member, "full_name")
			quiz_title = frappe.db.get_value("LMS Quiz", sub.quiz, "title")
			print(f"  - {member_name} ({sub.member}): {quiz_title}")

		assign_subs = frappe.get_all(
			"LMS Assignment Submission",
			{"member": ["in", student_list]},
			["name", "member", "assignment", "status"],
		)
		print(f"\nAssignment Submissions from these students: {len(assign_subs)}")
		for sub in assign_subs:
			member_name = frappe.db.get_value("User", sub.member, "full_name")
			assignment_title = frappe.db.get_value("LMS Assignment", sub.assignment, "title")
			print(f"  - {member_name} ({sub.member}): {assignment_title} (Status: {sub.status})")

		print(f"\n✓ Expected Pending: {len(quiz_subs)} quiz + {len(assign_subs)} assignments = {len(quiz_subs) + len(assign_subs)}")

	print("\n" + "=" * 80)
