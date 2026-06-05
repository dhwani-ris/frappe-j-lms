from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from lms.lms.custom.notifications import (
	MASTER_TRAINER_ROLE_PROFILE,
	check_course_deadline_reminders,
)


class TestCourseDeadlineReminders(FrappeTestCase):
	"""Tests for the daily "course deadline approaching" reminder.

	Invariant under test: when a batch's end_date is within the 2-day window and
	the enrolled employee has NOT completed the course, the student, their
	trainer(s), the master trainer(s) and the manager each receive an in-app
	notification AND an email. Completed courses and out-of-window batches
	produce nothing.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.company = self._get_company()

		self.student = self._user("dl_student@example.com", "Del", "Student", ["LMS Student"])
		self.trainer = self._user("dl_trainer@example.com", "Del", "Trainer", ["LMS Trainer"])
		self.manager = self._user("dl_manager@example.com", "Del", "Manager", ["LMS Manager"])
		self.master = self._master_trainer("dl_master@example.com", "Del", "Master")

		# Employee reporting line: student -> manager.
		mgr_emp = self._employee(self.manager.name, "Del Manager")
		self._employee(self.student.name, "Del Student", reports_to=mgr_emp)

		self.course = self._course("Deadline Reminder Test Course")
		# Auto-batch ending in exactly 2 days, with the trainer as instructor.
		self.batch = self._batch(self.course.name, self.trainer.name, days_to_end=2)
		self._batch_enroll(self.batch.name, self.student.name)
		self.enrollment = self._enroll(self.course.name, self.student.name, progress=40)

		# Start from a clean slate so assertions reflect only this run.
		self._clear_logs()

	# ── helpers ──────────────────────────────────────────────────────────────
	def _get_company(self):
		company = frappe.db.get_value("Company", {}, "name")
		if company:
			return company
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "Deadline Test Co",
				"abbr": "DTC",
				"default_currency": "INR",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		return doc.name

	def _user(self, email, first, last, roles):
		if frappe.db.exists("User", email):
			return frappe.get_doc("User", email)
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = first
		user.last_name = last
		user.user_type = "Website User"
		for role in roles:
			user.append("roles", {"role": role})
		user.save(ignore_permissions=True)
		return user

	def _master_trainer(self, email, first, last):
		if not frappe.db.exists("Role Profile", MASTER_TRAINER_ROLE_PROFILE):
			rp = frappe.new_doc("Role Profile")
			rp.role_profile = MASTER_TRAINER_ROLE_PROFILE
			rp.append("roles", {"role": "LMS Master Trainer"})
			rp.save(ignore_permissions=True)
		user = self._user(email, first, last, ["LMS Master Trainer"])
		user.role_profile_name = MASTER_TRAINER_ROLE_PROFILE
		user.save(ignore_permissions=True)
		return user

	def _employee(self, user_id, name, reports_to=None):
		existing = frappe.db.get_value("Employee", {"user_id": user_id}, "name")
		if existing:
			return existing
		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"employee_name": name,
				"first_name": name,
				"user_id": user_id,
				"status": "Active",
				"company": self.company,
				"date_of_joining": "2020-01-01",
				"date_of_birth": "1990-01-01",
				"gender": "Other",
				"reports_to": reports_to,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		return emp.name

	def _course(self, title):
		course = frappe.new_doc("LMS Course")
		course.title = title
		course.short_introduction = "x"
		course.description = "x"
		course.published = 1
		course.append("instructors", {"instructor": "Administrator"})
		course.save(ignore_permissions=True)
		return course

	def _batch(self, course, trainer, days_to_end):
		batch = frappe.new_doc("LMS Batch")
		batch.title = f"Deadline Batch {course} {days_to_end}"
		batch.start_date = nowdate()
		batch.end_date = add_days(nowdate(), days_to_end)
		batch.start_time = "09:00:00"
		batch.end_time = "18:00:00"
		batch.timezone = "Asia/Kolkata"
		batch.description = "x"
		batch.batch_details = "x"
		batch.published = 1
		batch.append("instructors", {"instructor": trainer})
		batch.append("courses", {"course": course})
		batch.save(ignore_permissions=True)
		return batch

	def _batch_enroll(self, batch, member):
		doc = frappe.new_doc("LMS Batch Enrollment")
		doc.batch = batch
		doc.member = member
		doc.save(ignore_permissions=True)

	def _enroll(self, course, member, progress):
		enrollment = frappe.new_doc("LMS Enrollment")
		enrollment.course = course
		enrollment.member = member
		enrollment.save(ignore_permissions=True)
		# progress is a read-only computed field; set directly.
		frappe.db.set_value("LMS Enrollment", enrollment.name, "progress", progress)
		return enrollment

	def _clear_logs(self):
		frappe.db.delete(
			"Notification Log", {"for_user": ["in", self._all_recipients()]}
		)

	def _all_recipients(self):
		return [self.student.name, self.trainer.name, self.manager.name, self.master.name]

	def _emailed_recipients(self, mock_sendmail):
		"""Recipients emailed *about our enrollment*. Scope by reference_name
		because master trainers are org-wide and may be emailed about other
		in-window batches that pre-exist in the test DB."""
		emailed = set()
		for call in mock_sendmail.call_args_list:
			if call.kwargs.get("reference_name") == self.enrollment.name:
				emailed.update(call.kwargs.get("recipients", []))
		return emailed

	def _logs_for(self, user):
		return frappe.get_all(
			"Notification Log",
			{"for_user": user, "document_name": self.enrollment.name},
			pluck="subject",
		)

	# ── tests ────────────────────────────────────────────────────────────────
	def test_all_four_recipients_get_notification_and_email(self):
		with patch("frappe.sendmail") as mock_sendmail:
			check_course_deadline_reminders()

		# In-app notification for every recipient.
		for user in self._all_recipients():
			self.assertEqual(
				len(self._logs_for(user)), 1, f"expected exactly one notification for {user}"
			)

		# Student gets the first-person message; stakeholders the third-person one.
		self.assertIn("is due", self._logs_for(self.student.name)[0])
		self.assertIn(
			"Del Student has not completed", self._logs_for(self.manager.name)[0]
		)

		# Email triggered to each recipient.
		emailed = self._emailed_recipients(mock_sendmail)
		for user in self._all_recipients():
			self.assertIn(user, emailed, f"expected an email to {user}")

	def test_completed_course_is_skipped(self):
		frappe.db.set_value("LMS Enrollment", self.enrollment.name, "progress", 100)
		with patch("frappe.sendmail") as mock_sendmail:
			check_course_deadline_reminders()

		for user in self._all_recipients():
			self.assertEqual(self._logs_for(user), [])
		emailed = self._emailed_recipients(mock_sendmail)
		self.assertEqual(emailed.intersection(self._all_recipients()), set())

	def test_batch_outside_window_is_skipped(self):
		# Push the deadline well beyond the 2-day window.
		frappe.db.set_value("LMS Batch", self.batch.name, "end_date", add_days(nowdate(), 10))
		with patch("frappe.sendmail") as mock_sendmail:
			check_course_deadline_reminders()

		for user in self._all_recipients():
			self.assertEqual(self._logs_for(user), [])
		emailed = self._emailed_recipients(mock_sendmail)
		self.assertEqual(emailed.intersection(self._all_recipients()), set())
