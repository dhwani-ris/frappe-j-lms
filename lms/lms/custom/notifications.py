import frappe
from frappe.utils import add_days, cint, date_diff, format_date, format_datetime, getdate, today
from frappe.utils.user import get_users_with_role

# Role profile that identifies a Master Trainer (set on the User while creating
# an employee at /lms/employees). Master Trainers are org-wide, so every enabled
# user carrying this role profile is notified about an at-risk assignment.
MASTER_TRAINER_ROLE_PROFILE = "Jamboree Master Trainer"

# Role that identifies HR. Querying by role (rather than role profile) also
# catches users who were granted "LMS HR" directly, without the Jamboree HR
# role profile.
HR_ROLE = "LMS HR"

# An assignment is "near its deadline" when the batch end_date is this many days
# away (or fewer). With a daily scheduler this yields a reminder on each of the
# final 3 days before the deadline (2 days left, 1 day left, due today).
DEADLINE_REMINDER_WINDOW_DAYS = 2

# Employee.status values that mean "this person no longer has LMS access" but
# has not (necessarily) left the organisation.
ACCESS_REVOKED_STATUSES = ("Inactive", "Suspended")


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
		# ignore_permissions: doc-event hook runs as the submitting student, who has
		# no write access to another user's Notification Log — written as the system.
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
		# ignore_permissions: doc-event hook runs as the completing student, who has
		# no write access to another user's Notification Log — written as the system.
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
			# ignore_permissions: doc-event hook runs as the completing student, who has
			# no write access to another user's Notification Log — written as the system.
			notification.save(ignore_permissions=True)


def check_course_deadline_reminders():
	"""Daily scheduled task: remind stakeholders about courses that are about to
	miss their deadline.

	For every batch whose ``end_date`` is 0, 1 or 2 days away, and for every
	(enrolled employee, course) pair in that batch where the course is **not yet
	completed** (``LMS Enrollment.progress < 100``), send both an in-app
	notification and an email to:

	* the **employee** (student) themselves,
	* the **trainer(s)** of that course — the instructors on the batch,
	* the **master trainer(s)** — users with the ``Jamboree Master Trainer``
	  role profile, and
	* the employee's **manager** — resolved via ``Employee.reports_to``.

	Because the job runs daily and the window is inclusive, an incomplete
	assignment is reminded once per day on each of the final three days before
	the deadline (escalating urgency: "2 days left" -> "tomorrow" -> "today").
	"""
	today_date = getdate(today())
	window_end = add_days(today_date, DEADLINE_REMINDER_WINDOW_DAYS)

	# Only batches whose deadline lands in the next 0..2 days (inclusive).
	batches = frappe.get_all(
		"LMS Batch",
		filters={"end_date": ["between", [today_date, window_end]]},
		fields=["name", "end_date"],
	)
	if not batches:
		return

	# Master trainers are org-wide: every enabled user carrying the role profile.
	master_trainers = _get_master_trainers()

	for batch in batches:
		days_left = date_diff(batch.end_date, today_date)

		courses = frappe.get_all(
			"Batch Course",
			{"parent": batch.name, "parenttype": "LMS Batch"},
			pluck="course",
		)
		members = frappe.get_all(
			"LMS Batch Enrollment", {"batch": batch.name}, pluck="member"
		)
		if not courses or not members:
			continue

		# Trainers for this assignment = the batch instructors.
		trainers = frappe.get_all(
			"Course Instructor",
			{"parent": batch.name, "parenttype": "LMS Batch"},
			pluck="instructor",
		)

		for member in members:
			for course in courses:
				progress = (
					frappe.db.get_value(
						"LMS Enrollment",
						{"member": member, "course": course},
						"progress",
					)
					or 0
				)
				if cint(progress) >= 100:
					continue  # already completed — no reminder needed

				_send_deadline_reminders(
					member=member,
					course=course,
					end_date=batch.end_date,
					days_left=days_left,
					trainers=trainers,
					master_trainers=master_trainers,
				)


def _send_deadline_reminders(member, course, end_date, days_left, trainers, master_trainers):
	"""Build the messages and fan them out to the student + all stakeholders."""
	student_name = frappe.db.get_value("User", member, "full_name") or member
	course_title = frappe.db.get_value("LMS Course", course, "title") or course
	enrollment = frappe.db.get_value(
		"LMS Enrollment", {"member": member, "course": course}, "name"
	)
	deadline = format_date(end_date)

	# Human-friendly phrasing for subject + body.
	if days_left <= 0:
		when = "today"
		remaining = "the deadline is today"
	elif days_left == 1:
		when = "tomorrow"
		remaining = "1 day remaining"
	else:
		when = f"in {days_left} days"
		remaining = f"{days_left} days remaining"

	# Resolve the employee's manager via the HR reporting line.
	manager_user = None
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": member, "status": "Active"},
		["reports_to"],
		as_dict=True,
	)
	if employee and employee.reports_to:
		manager_user = frappe.db.get_value("Employee", employee.reports_to, "user_id")

	# 1) Notify the student (first person).
	student_subject = f"Reminder: '{course_title}' is due {when}"
	student_message = (
		f"You have not yet completed the course <strong>{course_title}</strong>. "
		f"The deadline is <strong>{deadline}</strong> ({remaining}). "
		f"Please complete it before the due date."
	)
	_notify(member, member, student_subject, student_message, "LMS Enrollment", enrollment)

	# 2) Notify the stakeholders (third person), de-duplicated and excluding the
	#    student (who was already notified with a personalised message).
	stakeholders = set(filter(None, list(trainers) + list(master_trainers) + [manager_user]))
	stakeholders.discard(member)

	stake_subject = f"Reminder: {student_name} has not completed '{course_title}' (due {when})"
	stake_message = (
		f"<strong>{student_name}</strong> has not yet completed the course "
		f"<strong>{course_title}</strong>. The deadline is <strong>{deadline}</strong> "
		f"({remaining})."
	)
	for recipient in stakeholders:
		_notify(recipient, member, stake_subject, stake_message, "LMS Enrollment", enrollment)


def notify_on_employee_exit(doc, method=None):
	"""``Employee`` ``on_update`` hook: notify HR, the immediate manager and the
	master trainer(s) when an employee leaves the organisation or their LMS
	access is revoked.

	Fires on a **status transition** only (no spam on unrelated edits):

	* ``-> Left`` — the employee has exited the organisation.
	* ``-> Inactive`` / ``-> Suspended`` — the employee's LMS access has been
	  revoked (this is what HR's *Deactivate* action at /lms/employees sets;
	  it also disables the linked User account).
	"""
	prev = doc.get_doc_before_save()
	if not prev or prev.status == doc.status:
		return

	if doc.status == "Left":
		_send_exit_notifications(doc, event="exit")
	elif doc.status in ACCESS_REVOKED_STATUSES:
		_send_exit_notifications(doc, event="revoked")


def notify_on_user_disabled(doc, method=None):
	"""``User`` ``on_update`` hook: notify stakeholders when a user account is
	disabled directly (e.g. from the desk User form) — that, too, revokes LMS
	access.

	Skipped when the linked Employee is no longer Active: in that case the
	Employee status transition (``notify_on_employee_exit``) already covers the
	event. The HR *Deactivate* action disables the User via ``db.set_value``
	(which does not fire this hook) after updating the Employee, so the two
	paths never double-notify.
	"""
	prev = doc.get_doc_before_save()
	if not prev or cint(doc.enabled) or not cint(prev.enabled):
		return  # not a 1 -> 0 transition

	employee = frappe.db.get_value(
		"Employee",
		{"user_id": doc.name},
		["name", "employee_name", "user_id", "reports_to", "relieving_date", "status"],
		as_dict=True,
	)
	if not employee or employee.status != "Active":
		return

	_send_exit_notifications(
		employee, event="revoked", reason="Their user account was disabled."
	)


def notify_lms_access_revoked(employee_name, reason=None):
	"""Notify stakeholders that an employee's LMS access was revoked outside a
	status change — e.g. when HR removes the LMS role profile from the user
	(``dashboard_api.unassign_employee_role``)."""
	employee = frappe.db.get_value(
		"Employee",
		employee_name,
		["name", "employee_name", "user_id", "reports_to", "relieving_date"],
		as_dict=True,
	)
	if employee:
		_send_exit_notifications(employee, event="revoked", reason=reason)


def _send_exit_notifications(employee, event, reason=None):
	"""Fan out an employee-exit / access-revocation notification (in-app + email)
	to HR, the employee's immediate manager and the master trainer(s)."""
	employee_name = employee.employee_name or employee.name

	if event == "exit":
		relieved = (
			f" effective <strong>{format_date(employee.relieving_date)}</strong>"
			if employee.get("relieving_date")
			else ""
		)
		subject = f"Employee Exit: {employee_name} has left the organization"
		message = (
			f"<strong>{employee_name}</strong> has left the organization{relieved}. "
			f"Their LMS access stands revoked. Please complete any pending "
			f"offboarding steps (course handovers, batch reassignments, reporting-line updates)."
		)
	else:
		subject = f"Access Revoked: LMS access for {employee_name} has been revoked"
		message = (
			f"LMS access for <strong>{employee_name}</strong> has been revoked."
			+ (f" {reason}" if reason else "")
			+ " Please review their pending course assignments and reporting line."
		)

	# Immediate manager — resolved via the HR reporting line.
	manager_user = None
	if employee.get("reports_to"):
		manager_user = frappe.db.get_value("Employee", employee.reports_to, "user_id")
		if manager_user and not cint(frappe.db.get_value("User", manager_user, "enabled")):
			manager_user = None  # don't notify a disabled account

	# HR (org-wide, by role) + master trainers (org-wide, by role profile).
	recipients = set(get_users_with_role(HR_ROLE)) | set(_get_master_trainers())
	if manager_user:
		recipients.add(manager_user)

	# Never notify the exiting employee about their own exit.
	recipients.discard(employee.get("user_id"))
	recipients.discard(None)

	for recipient in recipients:
		_notify(recipient, frappe.session.user, subject, message, "Employee", employee.name)


def _get_master_trainers():
	"""All enabled users carrying the Master Trainer role profile (org-wide)."""
	return frappe.get_all(
		"User",
		filters={"role_profile_name": MASTER_TRAINER_ROLE_PROFILE, "enabled": 1},
		pluck="name",
	)


def _notify(recipient, from_user, subject, message, ref_doctype=None, ref_name=None):
	"""Create an in-app Notification Log entry and send an email to one recipient."""
	notification = frappe.new_doc("Notification Log")
	notification.for_user = recipient
	notification.from_user = from_user
	notification.type = "Alert"
	notification.subject = subject
	notification.email_content = message
	if ref_doctype and ref_name:
		notification.document_type = ref_doctype
		notification.document_name = ref_name
	# ignore_permissions: Notification Log must be written as the system — the recipient
	# is never the session user, and this helper is called from both scheduler and API contexts.
	notification.save(ignore_permissions=True)

	try:
		frappe.sendmail(
			recipients=[recipient],
			subject=subject,
			message=message,
			reference_doctype=ref_doctype if ref_name else None,
			reference_name=ref_name,
		)
	except Exception:
		# Never let a single failed email abort the whole run.
		frappe.log_error(title="LMS notification email failed")


# Employee Feedback Form — sessions scheduled
# -------------------------------------------
EMPLOYEE_FEEDBACK_DOCTYPE = "Employee Feedback Form"


def notify_feedback_scheduled(form):
	"""Sent when a Master Trainer confirms the feedback session schedule.

	Each participant (the immediate manager if any, every assigned trainer, and the
	master trainer) gets an in-app notification + email with *their* slot; the
	employee gets the full schedule. Times are owned by the Master Trainer, so this
	tells everyone when to show up.
	"""
	employee_name = form.employee_name or frappe.db.get_value(
		"Employee", form.employee, "employee_name"
	)
	course_title = form.course_title or frappe.db.get_value("LMS Course", form.course, "title")
	employee_user = frappe.db.get_value("Employee", form.employee, "user_id")
	from_user = form.master_trainer or "Administrator"

	def fmt(dt):
		return format_datetime(dt) if dt else "—"

	def slot(recipient, role_phrase, when):
		if not recipient or not when:
			return
		_notify(
			recipient,
			from_user,
			f"Feedback session scheduled with {employee_name}",
			(
				f"Your {role_phrase} for <strong>{employee_name}</strong> "
				f"({course_title}) is scheduled on <strong>{fmt(when)}</strong>."
			),
			EMPLOYEE_FEEDBACK_DOCTYPE,
			form.name,
		)

	# Manager
	if form.immediate_manager:
		manager_user = frappe.db.get_value("Employee", form.immediate_manager, "user_id")
		slot(manager_user, "manager feedback session", form.manager_meeting_datetime)

	# Each trainer
	for row in form.trainer_feedback:
		slot(row.trainer, "trainer feedback session", row.meeting_datetime)

	# Master trainer
	slot(form.master_trainer, "master-trainer feedback session", form.master_meeting_datetime)

	# Employee: the full schedule
	if employee_user:
		lines = []
		if form.immediate_manager and form.manager_meeting_datetime:
			lines.append(f"Manager: {fmt(form.manager_meeting_datetime)}")
		for row in form.trainer_feedback:
			if row.meeting_datetime:
				lines.append(
					f"Trainer ({row.trainer_name or row.trainer}): {fmt(row.meeting_datetime)}"
				)
		if form.master_meeting_datetime:
			lines.append(f"Master Trainer: {fmt(form.master_meeting_datetime)}")
		_notify(
			employee_user,
			from_user,
			f"Your feedback sessions for '{course_title}' are scheduled",
			(
				f"Your feedback sessions for <strong>{course_title}</strong> are scheduled:<br>"
				+ "<br>".join(lines)
			),
			EMPLOYEE_FEEDBACK_DOCTYPE,
			form.name,
		)
