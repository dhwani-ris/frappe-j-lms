# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from lms.lms.custom import employee_feedback as ef
from lms.lms.custom.notifications import MASTER_TRAINER_ROLE_PROFILE

DOCTYPE = "Employee Feedback Form"


class TestEmployeeFeedbackForm(FrappeTestCase):
	"""End-to-end behaviour of the Employee Feedback Form.

	Covers auto-creation, the Master-Trainer scheduling phase (order / gap / future /
	conflict validation, MT-only, lock + reschedule), the scheduled-feedback record
	flow, the completion gate + lock + reopen, and row-level permission scoping.
	"""

	# Learners whose forms this suite creates. Cleanup is scoped to these so we never
	# touch real feedback forms living on the shared site.
	TEST_LEARNER_EMAILS = (
		"eff_learner@example.com",
		"eff_conf1@example.com",
		"eff_conf2@example.com",
		"eff_nomgr@example.com",
	)

	def _cleanup_forms(self):
		"""Delete only this suite's feedback forms and commit — some hooks
		(enqueue / sendmail) commit mid-test, so rollback alone can't isolate us."""
		frappe.set_user("Administrator")
		emps = frappe.get_all(
			"Employee", {"user_id": ["in", self.TEST_LEARNER_EMAILS]}, pluck="name"
		)
		if emps:
			for name in frappe.get_all(DOCTYPE, {"employee": ["in", emps]}, pluck="name"):
				frappe.delete_doc(DOCTYPE, name, force=True, ignore_permissions=True)
			frappe.db.commit()

	def tearDown(self):
		self._cleanup_forms()

	def setUp(self):
		frappe.set_user("Administrator")
		self.company = self._company()
		self._cleanup_forms()

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
		batch.title = f"EFF Batch {course} {trainer}"
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

	def _complete(self, enrollment=None, employee=None, course=None):
		"""Drive the enrollment to 100% via a real save so the on_update hook fires."""
		enr = frappe.get_doc("LMS Enrollment", (enrollment or self.enrollment).name)
		enr.progress = 100
		enr.save(ignore_permissions=True)
		name = frappe.db.get_value(
			DOCTYPE,
			{"employee": employee or self.emp_learner, "course": course or self.course.name},
		)
		return frappe.get_doc(DOCTYPE, name) if name else None

	def _times(self, base_days=1, gap=20):
		"""Valid future schedule: manager < trainer < master, ≥15 min apart."""
		base = add_to_date(now_datetime(), days=base_days)
		return {
			"manager": base,
			"trainer": add_to_date(base, minutes=gap),
			"master": add_to_date(base, minutes=2 * gap),
		}

	def _schedule(self, form, times=None, as_user=None, trainer_overrides=None):
		as_user = as_user or self.master.name
		times = times or self._times()
		overrides = trainer_overrides or {}
		trainer_times = [
			{
				"trainer": r.trainer,
				"meeting_datetime": overrides.get(r.trainer, times.get("trainer")),
			}
			for r in form.trainer_feedback
		]
		frappe.set_user(as_user)
		try:
			return ef.schedule_sessions(
				form.name,
				manager_meeting_datetime=times.get("manager"),
				master_meeting_datetime=times.get("master"),
				trainer_times=trainer_times,
			)
		finally:
			frappe.set_user("Administrator")

	def _as(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	# ── auto-creation ───────────────────────────────────────────────────────
	def test_auto_creation_prefills_trainers_and_manager(self):
		form = self._complete()
		self.assertIsNotNone(form, "a feedback form should be auto-created on 100%")
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)
		self.assertEqual(form.batch, self.batch.name)
		self.assertEqual(form.completed_on, frappe.utils.getdate(nowdate()))
		self.assertEqual(form.immediate_manager, self.emp_manager)
		self.assertEqual([r.trainer for r in form.trainer_feedback], [self.trainer.name])

	def test_idempotent_no_duplicate(self):
		self._complete()
		self._complete()
		self.assertEqual(
			frappe.db.count(DOCTYPE, {"employee": self.emp_learner, "course": self.course.name}),
			1,
		)

	def test_self_enrolled_without_batch_gets_no_form(self):
		course2 = self._course("EFF Self Enrolled Course")
		enr = self._enroll(course2.name, self.learner.name)
		enr.progress = 100
		enr.save(ignore_permissions=True)
		self.assertFalse(
			frappe.db.exists(DOCTYPE, {"employee": self.emp_learner, "course": course2.name})
		)

	# ── scheduling ────────────────────────────────────────────────────────────
	def test_feedback_blocked_before_scheduling(self):
		form = self._complete()
		with self.assertRaises(frappe.ValidationError):
			self._as(self.manager.name, ef.save_manager_feedback, form.name, "too early")

	def test_only_master_or_admin_can_schedule(self):
		form = self._complete()
		t = self._times()
		frappe.set_user(self.manager.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				ef.schedule_sessions(
					form.name,
					manager_meeting_datetime=t["manager"],
					master_meeting_datetime=t["master"],
					trainer_times=[{"trainer": self.trainer.name, "meeting_datetime": t["trainer"]}],
				)
		finally:
			frappe.set_user("Administrator")

	def test_schedule_sets_state_and_master_trainer(self):
		form = self._complete()
		self._schedule(form)
		form.reload()
		self.assertTrue(form.sessions_scheduled)
		self.assertEqual(form.status, "Sessions Scheduled")
		self.assertEqual(form.master_trainer, self.master.name)
		self.assertTrue(form.manager_meeting_datetime)
		self.assertTrue(form.trainer_feedback[0].meeting_datetime)
		self.assertTrue(form.master_meeting_datetime)

	def test_schedule_rejects_bad_order(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=1)
		bad = {
			"manager": add_to_date(base, minutes=60),  # manager AFTER trainer
			"trainer": add_to_date(base, minutes=20),
			"master": add_to_date(base, minutes=120),
		}
		with self.assertRaises(frappe.ValidationError):
			self._schedule(form, times=bad)

	def test_schedule_rejects_small_gap(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=1)
		bad = {
			"manager": base,
			"trainer": add_to_date(base, minutes=5),  # <15 min after manager
			"master": add_to_date(base, minutes=40),
		}
		with self.assertRaises(frappe.ValidationError):
			self._schedule(form, times=bad)

	def test_schedule_rejects_past_time(self):
		form = self._complete()
		base = add_to_date(now_datetime(), minutes=-120)
		bad = {
			"manager": base,
			"trainer": add_to_date(base, minutes=20),
			"master": add_to_date(base, minutes=40),
		}
		with self.assertRaises(frappe.ValidationError):
			self._schedule(form, times=bad)

	def test_schedule_rejects_missing_time(self):
		form = self._complete()
		t = self._times()
		t["master"] = None  # missing master slot
		with self.assertRaises(frappe.ValidationError):
			self._schedule(form, times=t)

	def test_cross_form_conflict_for_shared_trainer(self):
		# Two no-manager learners sharing the same trainer; overlapping trainer slots clash.
		l1 = self._user("eff_conf1@example.com", "Conf", "One", ["LMS Student"])
		l2 = self._user("eff_conf2@example.com", "Conf", "Two", ["LMS Student"])
		e1 = self._employee(l1.name, "Conf One")  # no reports_to
		e2 = self._employee(l2.name, "Conf Two")
		c1 = self._course("EFF Conflict 1")
		c2 = self._course("EFF Conflict 2")
		b1 = self._batch(c1.name, self.trainer.name)
		b2 = self._batch(c2.name, self.trainer.name)
		self._batch_enroll(b1.name, l1.name)
		self._batch_enroll(b2.name, l2.name)
		enr1 = self._enroll(c1.name, l1.name)
		enr2 = self._enroll(c2.name, l2.name)
		f1 = self._complete(enr1, employee=e1, course=c1.name)
		f2 = self._complete(enr2, employee=e2, course=c2.name)

		base = add_to_date(now_datetime(), days=5)
		# f1: no manager → trainer then master, far apart.
		self._schedule(
			f1,
			times={
				"manager": None,
				"trainer": add_to_date(base, minutes=20),
				"master": add_to_date(base, minutes=200),
			},
		)
		# f2: trainer overlaps f1's trainer slot (5 min apart) → conflict.
		with self.assertRaises(frappe.ValidationError):
			self._schedule(
				f2,
				times={
					"manager": None,
					"trainer": add_to_date(base, minutes=25),
					"master": add_to_date(base, minutes=400),
				},
			)

	# ── record flow ─────────────────────────────────────────────────────────
	def test_full_flow_to_completion_then_lock_and_reopen(self):
		form = self._complete()
		self._schedule(form)

		self._as(self.manager.name, ef.save_manager_feedback, form.name, "Good.")
		self._as(self.trainer.name, ef.save_trainer_feedback, form.name, "Mock cleared.")
		form.reload()
		self.assertEqual(form.status, "Trainer Feedback Added")

		# Completion gate trips while master feedback is missing.
		with self.assertRaises(frappe.ValidationError):
			self._as(self.master.name, ef.complete_feedback, form.name)

		self._as(self.master.name, ef.save_master_feedback, form.name, "Endorsed.")
		self._as(self.master.name, ef.complete_feedback, form.name)
		form.reload()
		self.assertEqual(form.status, "Completed")
		self.assertEqual(form.master_feedback_by, self.master.name)

		# Locked: further edits are blocked.
		with self.assertRaises(frappe.ValidationError):
			self._as(self.manager.name, ef.save_manager_feedback, form.name, "edit after lock")

		# HR reopens for corrections → back to Draft, unscheduled.
		ef.reopen_feedback(form.name)
		form.reload()
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)

	def test_master_feedback_restricted_to_assigned_master(self):
		other_master = self._master_trainer("eff_master2@example.com", "Eff", "Master2")
		form = self._complete()
		self._schedule(form)  # self.master self-assigns
		with self.assertRaises(frappe.PermissionError):
			self._as(other_master.name, ef.save_master_feedback, form.name, "nope")
		with self.assertRaises(frappe.PermissionError):
			self._as(other_master.name, ef.complete_feedback, form.name)

	def test_reschedule_returns_to_draft_and_keeps_feedback(self):
		form = self._complete()
		self._schedule(form)
		self._as(self.manager.name, ef.save_manager_feedback, form.name, "Solid progress.")

		ef.reschedule_sessions(form.name)  # as Administrator (admin)
		form.reload()
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)
		self.assertIn("Solid progress", form.manager_feedback or "")

	def test_no_manager_form_schedules_and_completes_without_manager(self):
		learner = self._user("eff_nomgr@example.com", "No", "Manager", ["LMS Student"])
		emp = self._employee(learner.name, "No Manager Emp")  # no reports_to
		course = self._course("EFF No Manager Course")
		batch = self._batch(course.name, self.trainer.name)
		self._batch_enroll(batch.name, learner.name)
		enr = self._enroll(course.name, learner.name)
		form = self._complete(enr, employee=emp, course=course.name)
		self.assertFalse(form.immediate_manager)

		t = self._times()
		t["manager"] = None  # no manager slot
		self._schedule(form, times=t)
		form.reload()
		self.assertEqual(form.status, "Sessions Scheduled")

		self._as(self.trainer.name, ef.save_trainer_feedback, form.name, "Mock done.")
		self._as(self.master.name, ef.save_master_feedback, form.name, "Endorsed.")
		self._as(self.master.name, ef.complete_feedback, form.name)
		form.reload()
		self.assertEqual(form.status, "Completed")

	# ── permissions ───────────────────────────────────────────────────────────
	def test_trainer_cannot_record_other_trainers_row(self):
		form = self._complete()
		self._schedule(form)
		with self.assertRaises(Exception):
			self._as(self.outsider.name, ef.save_trainer_feedback, form.name, "nope")

	def test_permission_scoping(self):
		form = self._complete()

		frappe.set_user(self.trainer.name)
		try:
			visible = frappe.get_list(DOCTYPE, pluck="name")
		finally:
			frappe.set_user("Administrator")
		self.assertIn(form.name, visible)

		frappe.set_user(self.outsider.name)
		try:
			visible = frappe.get_list(DOCTYPE, pluck="name")
		except frappe.PermissionError:
			visible = []
		finally:
			frappe.set_user("Administrator")
		self.assertNotIn(form.name, visible)

	# ── notifications ───────────────────────────────────────────────────────
	def test_notifications_on_creation(self):
		with patch("frappe.sendmail"):
			form = self._complete()
		for user in (self.manager.name, self.trainer.name):
			logs = frappe.get_all(
				"Notification Log",
				{"for_user": user, "document_name": form.name, "document_type": DOCTYPE},
				pluck="name",
			)
			self.assertTrue(logs, f"expected a creation notification for {user}")

	def test_notifications_on_schedule(self):
		form = self._complete()
		with patch("frappe.sendmail"):
			self._schedule(form)
		# Manager, trainer, master and the employee each get a "scheduled" notification.
		for user in (self.manager.name, self.trainer.name, self.master.name, self.learner.name):
			logs = frappe.get_all(
				"Notification Log",
				{
					"for_user": user,
					"document_name": form.name,
					"subject": ["like", "%scheduled%"],
				},
				pluck="name",
			)
			self.assertTrue(logs, f"expected a schedule notification for {user}")
