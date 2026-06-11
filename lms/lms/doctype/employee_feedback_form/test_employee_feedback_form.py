# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, nowdate

from lms.lms.custom import employee_feedback as ef
from lms.lms.custom.notifications import MASTER_TRAINER_ROLE_PROFILE

DOCTYPE = "Employee Feedback Form"


class TestEmployeeFeedbackForm(FrappeTestCase):
	"""End-to-end behaviour of the Employee Feedback Form.

	Covers auto-creation on 100% completion (assigned employees only), idempotency,
	the manager/trainer/master record flow, the completion gate + lock, reopen, and
	row-level permission scoping.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.company = self._company()

		self.learner = self._user("eff_learner@example.com", "Eff", "Learner", ["LMS Student"])
		self.manager = self._user("eff_manager@example.com", "Eff", "Manager", ["LMS Manager"])
		self.trainer = self._user("eff_trainer@example.com", "Eff", "Trainer", ["LMS Trainer"])
		self.master = self._master_trainer("eff_master@example.com", "Eff", "Master")
		self.outsider = self._user("eff_outsider@example.com", "Eff", "Outsider", ["LMS Student"])

		self.emp_manager = self._employee(self.manager.name, "Eff Manager")
		self.emp_learner = self._employee(
			self.learner.name, "Eff Learner", reports_to=self.emp_manager
		)

		self.course = self._course("EFF Test Course")
		self.batch = self._batch(self.course.name, self.trainer.name)
		self._batch_enroll(self.batch.name, self.learner.name)
		self.enrollment = self._enroll(self.course.name, self.learner.name)

	# ── helpers ───────────────────────────────────────────────────────────────
	def _company(self):
		company = frappe.db.get_value("Company", {}, "name")
		if company:
			return company
		return (
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": "EFF Test Co",
					"abbr": "EFFC",
					"default_currency": "INR",
				}
			)
			.insert(ignore_permissions=True, ignore_mandatory=True)
			.name
		)

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
		return (
			frappe.get_doc(
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
			)
			.insert(ignore_permissions=True, ignore_mandatory=True)
			.name
		)

	def _course(self, title):
		course = frappe.new_doc("LMS Course")
		course.title = title
		course.short_introduction = "x"
		course.description = "x"
		course.published = 1
		course.append("instructors", {"instructor": "Administrator"})
		course.save(ignore_permissions=True)
		return course

	def _batch(self, course, trainer):
		batch = frappe.new_doc("LMS Batch")
		batch.title = f"EFF Batch {course}"
		batch.start_date = nowdate()
		batch.end_date = add_days(nowdate(), 30)
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
		frappe.get_doc(
			{"doctype": "LMS Batch Enrollment", "batch": batch, "member": member}
		).save(ignore_permissions=True)

	def _enroll(self, course, member):
		return frappe.get_doc(
			{"doctype": "LMS Enrollment", "course": course, "member": member}
		).save(ignore_permissions=True)

	def _complete(self, enrollment=None):
		"""Drive the enrollment to 100% via a real save so the on_update hook fires."""
		enr = frappe.get_doc("LMS Enrollment", (enrollment or self.enrollment).name)
		enr.progress = 100
		enr.save(ignore_permissions=True)
		return self._form()

	def _form(self):
		name = frappe.db.get_value(
			DOCTYPE, {"employee": self.emp_learner, "course": self.course.name}
		)
		return frappe.get_doc(DOCTYPE, name) if name else None

	# ── auto-creation ───────────────────────────────────────────────────────
	def test_auto_creation_prefills_trainers_and_manager(self):
		form = self._complete()
		self.assertIsNotNone(form, "a feedback form should be auto-created on 100%")
		self.assertEqual(form.status, "Draft")
		self.assertEqual(form.batch, self.batch.name)
		self.assertEqual(form.completed_on, frappe.utils.getdate(nowdate()))
		self.assertEqual(form.immediate_manager, self.emp_manager)
		self.assertEqual([r.trainer for r in form.trainer_feedback], [self.trainer.name])

	def test_idempotent_no_duplicate(self):
		self._complete()
		self._complete()  # re-save at 100% again
		self.assertEqual(
			frappe.db.count(DOCTYPE, {"employee": self.emp_learner, "course": self.course.name}),
			1,
		)

	def test_non_employee_learner_gets_no_form(self):
		# Outsider has no Employee record.
		self._batch_enroll(self.batch.name, self.outsider.name)
		enr = self._enroll(self.course.name, self.outsider.name)
		enr.progress = 100
		enr.save(ignore_permissions=True)
		self.assertFalse(
			frappe.db.exists(DOCTYPE, {"course": self.course.name, "employee": ["is", "not set"]})
		)
		self.assertFalse(
			frappe.db.get_value(
				"Employee", {"user_id": self.outsider.name}, "name"
			),
			"sanity: outsider is not an employee",
		)

	def test_self_enrolled_without_batch_gets_no_form(self):
		course2 = self._course("EFF Self Enrolled Course")
		enr = self._enroll(course2.name, self.learner.name)  # no micro-batch for this course
		enr.progress = 100
		enr.save(ignore_permissions=True)
		self.assertFalse(
			frappe.db.exists(DOCTYPE, {"employee": self.emp_learner, "course": course2.name})
		)

	# ── record flow ───────────────────────────────────────────────────────────
	def test_manager_feedback_flow(self):
		form = self._complete()
		frappe.set_user(self.manager.name)
		try:
			ef.save_manager_feedback(form.name, now_datetime(), "Solid progress.")
		finally:
			frappe.set_user("Administrator")
		form.reload()
		self.assertTrue(form.manager_feedback_done)
		self.assertEqual(form.manager_feedback_by, self.manager.name)
		self.assertEqual(form.status, "Manager Feedback Added")

	def test_full_flow_to_completion_then_lock_and_reopen(self):
		form = self._complete()

		# Manager
		frappe.set_user(self.manager.name)
		ef.save_manager_feedback(form.name, now_datetime(), "Good.")
		frappe.set_user("Administrator")

		# Trainer
		frappe.set_user(self.trainer.name)
		ef.save_trainer_feedback(form.name, now_datetime(), "Mock cleared.")
		frappe.set_user("Administrator")
		form.reload()
		self.assertEqual(form.status, "Trainer Feedback Added")

		# Completion gate trips while master feedback is missing.
		frappe.set_user(self.master.name)
		with self.assertRaises(frappe.ValidationError):
			ef.complete_feedback(form.name)

		# Master records, then completes.
		ef.save_master_feedback(form.name, now_datetime(), "Endorsed.")
		ef.complete_feedback(form.name)
		frappe.set_user("Administrator")
		form.reload()
		self.assertEqual(form.status, "Completed")
		self.assertEqual(form.master_feedback_by, self.master.name)

		# Locked: further edits are blocked.
		frappe.set_user(self.manager.name)
		with self.assertRaises(frappe.ValidationError):
			ef.save_manager_feedback(form.name, now_datetime(), "edit after lock")
		frappe.set_user("Administrator")

		# HR reopens for corrections.
		ef.reopen_feedback(form.name)
		form.reload()
		self.assertEqual(form.status, "Draft")

	def test_trainer_cannot_record_other_trainers_row(self):
		form = self._complete()
		frappe.set_user(self.outsider.name)  # not a trainer on this form
		try:
			with self.assertRaises(Exception):
				ef.save_trainer_feedback(form.name, now_datetime(), "nope")
		finally:
			frappe.set_user("Administrator")

	# ── permissions ───────────────────────────────────────────────────────────
	def test_permission_scoping(self):
		form = self._complete()

		# Trainer sees the form (get_list applies role perms + the permission query;
		# get_all would bypass permissions entirely).
		frappe.set_user(self.trainer.name)
		try:
			visible = frappe.get_list(DOCTYPE, pluck="name")
		finally:
			frappe.set_user("Administrator")
		self.assertIn(form.name, visible)

		# An unrelated student does not — they have no role read perm at all, so the
		# list is either empty or access is denied outright.
		frappe.set_user(self.outsider.name)
		try:
			visible = frappe.get_list(DOCTYPE, pluck="name")
		except frappe.PermissionError:
			visible = []
		finally:
			frappe.set_user("Administrator")
		self.assertNotIn(form.name, visible)

	def test_notifications_on_creation(self):
		with patch("frappe.sendmail"):
			form = self._complete()
		# Manager + trainer each get an in-app notification about the new form.
		for user in (self.manager.name, self.trainer.name):
			logs = frappe.get_all(
				"Notification Log",
				{"for_user": user, "document_name": form.name, "document_type": DOCTYPE},
				pluck="name",
			)
			self.assertTrue(logs, f"expected a creation notification for {user}")
