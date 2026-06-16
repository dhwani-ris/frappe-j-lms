# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from lms.lms.custom import course_assignment as ca
from lms.lms.custom import employee_feedback as ef
from lms.lms.custom.notifications import MASTER_TRAINER_ROLE_PROFILE

DOCTYPE = "Employee Feedback Form"


class TestEmployeeFeedbackForm(FrappeTestCase):
	"""End-to-end behaviour of the Employee Feedback Form, including the Master-Trainer
	scheduling phase with multiple manager/master sessions."""

	TEST_LEARNER_EMAILS = (
		"eff_learner@example.com",
		"eff_conf1@example.com",
		"eff_conf2@example.com",
		"eff_nomgr@example.com",
	)

	def _cleanup_forms(self):
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
		# Pin the baseline reporting line (a prior manager-sync test may have changed it,
		# and commits from hooks can leak across the suite).
		frappe.db.set_value("Employee", self.emp_learner, "reports_to", self.emp_manager)

		self.course = self._course("EFF Test Course")
		self.batch = self._batch(self.course.name, self.trainer.name)
		self._batch_enroll(self.batch.name, self.learner.name)
		self.enrollment = self._enroll(self.course.name, self.learner.name)

	# ── builders ──────────────────────────────────────────────────────────────
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
		enr = frappe.get_doc("LMS Enrollment", (enrollment or self.enrollment).name)
		enr.progress = 100
		enr.save(ignore_permissions=True)
		name = frappe.db.get_value(
			DOCTYPE,
			{"employee": employee or self.emp_learner, "course": course or self.course.name},
		)
		return frappe.get_doc(DOCTYPE, name) if name else None

	# ── scheduling helpers ────────────────────────────────────────────────────
	def _schedule(self, form, manager=None, trainer=None, master=None, as_user=None):
		"""Schedule with valid defaults: 1 manager, the trainer, 1 master — each 20 min
		apart, all tomorrow. Pass lists/values to override."""
		base = add_to_date(now_datetime(), days=1)
		if manager is None:
			manager = [base] if form.immediate_manager else []
		if trainer is None:
			trainer = add_to_date(base, minutes=20)
		if master is None:
			master = [add_to_date(base, minutes=40)]

		manager_times = [{"meeting_datetime": dt} for dt in manager]
		master_times = [{"meeting_datetime": dt} for dt in master]
		trainer_times = [
			{"trainer": r.trainer, "meeting_datetime": trainer} for r in form.trainer_feedback
		]
		frappe.set_user(as_user or self.master.name)
		try:
			return ef.schedule_sessions(
				form.name,
				manager_times=manager_times,
				master_times=master_times,
				trainer_times=trainer_times,
			)
		finally:
			frappe.set_user("Administrator")

	def _record_all(self, form):
		form.reload()
		for n in [s.name for s in form.manager_sessions]:
			self._as(self.manager.name, ef.save_manager_feedback, form.name, "Manager note.", n)
		for tr in [r.trainer for r in form.trainer_feedback]:
			self._as(tr, ef.save_trainer_feedback, form.name, "Trainer note.")
		form.reload()
		for n in [s.name for s in form.master_sessions]:
			self._as(self.master.name, ef.save_master_feedback, form.name, "Master note.", n)

	def _as(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	# ── auto-creation ───────────────────────────────────────────────────────
	def test_auto_creation_prefills_trainers_and_manager(self):
		form = self._complete()
		self.assertIsNotNone(form)
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)
		self.assertEqual(form.immediate_manager, self.emp_manager)
		self.assertEqual([r.trainer for r in form.trainer_feedback], [self.trainer.name])
		self.assertEqual(len(form.manager_sessions), 0)
		self.assertEqual(len(form.master_sessions), 0)

	def test_idempotent_no_duplicate(self):
		self._complete()
		self._complete()
		self.assertEqual(
			frappe.db.count(DOCTYPE, {"employee": self.emp_learner, "course": self.course.name}),
			1,
		)

	# ── scheduling ────────────────────────────────────────────────────────────
	def test_feedback_blocked_before_scheduling(self):
		form = self._complete()
		with self.assertRaises(frappe.ValidationError):
			self._as(self.manager.name, ef.save_manager_feedback, form.name, "too early", "x")

	def test_only_master_or_admin_can_schedule(self):
		form = self._complete()
		with self.assertRaises(frappe.PermissionError):
			self._schedule(form, as_user=self.manager.name)

	def test_schedule_sets_state_and_master_trainer(self):
		form = self._complete()
		self._schedule(form)
		form.reload()
		self.assertTrue(form.sessions_scheduled)
		self.assertEqual(form.status, "Sessions Scheduled")
		self.assertEqual(form.master_trainer, self.master.name)
		self.assertEqual(len(form.manager_sessions), 1)
		self.assertEqual(len(form.master_sessions), 1)

	def test_multiple_manager_and_master_sessions(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=2)
		# 2 manager, trainer, 2 master — strict group order, 20 min apart.
		self._schedule(
			form,
			manager=[base, add_to_date(base, minutes=20)],
			trainer=add_to_date(base, minutes=40),
			master=[add_to_date(base, minutes=60), add_to_date(base, minutes=80)],
		)
		form.reload()
		self.assertEqual(len(form.manager_sessions), 2)
		self.assertEqual(len(form.master_sessions), 2)

	def test_schedule_rejects_bad_order(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=1)
		with self.assertRaises(frappe.ValidationError):
			self._schedule(
				form,
				manager=[add_to_date(base, minutes=60)],  # manager AFTER trainer
				trainer=add_to_date(base, minutes=20),
				master=[add_to_date(base, minutes=120)],
			)

	def test_schedule_rejects_small_gap(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=1)
		with self.assertRaises(frappe.ValidationError):
			self._schedule(
				form,
				manager=[base, add_to_date(base, minutes=5)],  # two manager sessions 5 min apart
				trainer=add_to_date(base, minutes=40),
				master=[add_to_date(base, minutes=60)],
			)

	def test_schedule_rejects_past_time(self):
		form = self._complete()
		base = add_to_date(now_datetime(), minutes=-120)
		with self.assertRaises(frappe.ValidationError):
			self._schedule(
				form,
				manager=[base],
				trainer=add_to_date(base, minutes=20),
				master=[add_to_date(base, minutes=40)],
			)

	def test_schedule_requires_a_master_session(self):
		form = self._complete()
		with self.assertRaises(frappe.ValidationError):
			self._schedule(form, master=[])

	def test_cross_form_conflict_for_shared_trainer(self):
		l1 = self._user("eff_conf1@example.com", "Conf", "One", ["LMS Student"])
		l2 = self._user("eff_conf2@example.com", "Conf", "Two", ["LMS Student"])
		e1 = self._employee(l1.name, "Conf One")
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
		# f1: no manager → trainer then master.
		self._schedule(
			f1,
			manager=[],
			trainer=add_to_date(base, minutes=20),
			master=[add_to_date(base, minutes=200)],
		)
		# f2: trainer overlaps f1's trainer slot (5 min apart) → conflict.
		with self.assertRaises(frappe.ValidationError):
			self._schedule(
				f2,
				manager=[],
				trainer=add_to_date(base, minutes=25),
				master=[add_to_date(base, minutes=400)],
			)

	# ── record flow ─────────────────────────────────────────────────────────
	def test_full_flow_to_completion_then_lock_and_reopen(self):
		form = self._complete()
		self._schedule(form)
		self._record_all(form)
		form.reload()
		self.assertEqual(form.status, "Trainer Feedback Added")

		self._as(self.master.name, ef.complete_feedback, form.name)
		form.reload()
		self.assertEqual(form.status, "Completed")
		self.assertTrue(all(s.recorded for s in form.master_sessions))
		self.assertEqual(form.master_sessions[0].recorded_by, self.master.name)

		# Locked.
		with self.assertRaises(frappe.ValidationError):
			self._as(
				self.manager.name,
				ef.save_manager_feedback,
				form.name,
				"edit after lock",
				form.manager_sessions[0].name,
			)

		ef.reopen_feedback(form.name)
		form.reload()
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)

	def test_completion_requires_all_manager_sessions(self):
		form = self._complete()
		base = add_to_date(now_datetime(), days=2)
		self._schedule(
			form,
			manager=[base, add_to_date(base, minutes=20)],
			trainer=add_to_date(base, minutes=40),
			master=[add_to_date(base, minutes=60)],
		)
		form.reload()
		# Record only the FIRST manager session, all trainers, the master.
		self._as(
			self.manager.name, ef.save_manager_feedback, form.name, "fb1", form.manager_sessions[0].name
		)
		self._as(self.trainer.name, ef.save_trainer_feedback, form.name, "trn")
		self._as(
			self.master.name, ef.save_master_feedback, form.name, "mst", form.master_sessions[0].name
		)
		with self.assertRaises(frappe.ValidationError):
			self._as(self.master.name, ef.complete_feedback, form.name)
		# Record the second manager session → now completes.
		form.reload()
		self._as(
			self.manager.name, ef.save_manager_feedback, form.name, "fb2", form.manager_sessions[1].name
		)
		self._as(self.master.name, ef.complete_feedback, form.name)
		form.reload()
		self.assertEqual(form.status, "Completed")

	def test_master_feedback_restricted_to_assigned_master(self):
		other_master = self._master_trainer("eff_master2@example.com", "Eff", "Master2")
		form = self._complete()
		self._schedule(form)
		form.reload()
		row = form.master_sessions[0].name
		with self.assertRaises(frappe.PermissionError):
			self._as(other_master.name, ef.save_master_feedback, form.name, "nope", row)
		with self.assertRaises(frappe.PermissionError):
			self._as(other_master.name, ef.complete_feedback, form.name)

	def test_reschedule_returns_to_draft_and_keeps_feedback(self):
		form = self._complete()
		self._schedule(form)
		form.reload()
		self._as(
			self.manager.name,
			ef.save_manager_feedback,
			form.name,
			"Solid progress.",
			form.manager_sessions[0].name,
		)
		ef.reschedule_sessions(form.name)
		form.reload()
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)
		self.assertIn("Solid progress", form.manager_sessions[0].feedback or "")

	def test_no_manager_form_schedules_and_completes_without_manager(self):
		learner = self._user("eff_nomgr@example.com", "No", "Manager", ["LMS Student"])
		emp = self._employee(learner.name, "No Manager Emp")
		course = self._course("EFF No Manager Course")
		batch = self._batch(course.name, self.trainer.name)
		self._batch_enroll(batch.name, learner.name)
		enr = self._enroll(course.name, learner.name)
		form = self._complete(enr, employee=emp, course=course.name)
		self.assertFalse(form.immediate_manager)

		self._schedule(form, manager=[])
		form.reload()
		self.assertEqual(form.status, "Sessions Scheduled")
		self.assertEqual(len(form.manager_sessions), 0)

		self._as(self.trainer.name, ef.save_trainer_feedback, form.name, "Mock done.")
		self._as(
			self.master.name, ef.save_master_feedback, form.name, "Endorsed.", form.master_sessions[0].name
		)
		self._as(self.master.name, ef.complete_feedback, form.name)
		form.reload()
		self.assertEqual(form.status, "Completed")

	# ── permissions ───────────────────────────────────────────────────────────
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
		for user in (self.manager.name, self.trainer.name, self.master.name, self.learner.name):
			logs = frappe.get_all(
				"Notification Log",
				{"for_user": user, "document_name": form.name, "subject": ["like", "%scheduled%"]},
				pluck="name",
			)
			self.assertTrue(logs, f"expected a schedule notification for {user}")

	# ── edit trainers ─────────────────────────────────────────────────────────
	def _schedule_spaced(self, form):
		"""Schedule a (possibly multi-trainer) form: manager → trainers → master, 20 min apart."""
		base = add_to_date(now_datetime(), days=1)
		slot = [0]

		def at():
			t = add_to_date(base, minutes=slot[0] * 20)
			slot[0] += 1
			return t

		mt = [{"meeting_datetime": at()}] if form.immediate_manager else []
		tt = [{"trainer": r.trainer, "meeting_datetime": at()} for r in form.trainer_feedback]
		xt = [{"meeting_datetime": at()}]
		self._as(self.master.name, ef.schedule_sessions, form.name, mt, xt, tt)

	def test_add_trainer_unschedules_scheduled_form(self):
		form = self._complete()
		self._schedule(form)
		trainer2 = self._user("eff_trainer2@example.com", "Eff", "Trainer2", ["LMS Trainer"])
		with patch("frappe.sendmail"):
			ef.sync_assignment_trainers_to_feedback(self.batch.name, [self.trainer.name, trainer2.name])
		form.reload()
		self.assertEqual(
			{r.trainer for r in form.trainer_feedback}, {self.trainer.name, trainer2.name}
		)
		self.assertEqual(form.status, "Draft")
		self.assertFalse(form.sessions_scheduled)

	def test_remove_unrecorded_trainer_drops_and_keeps_schedule(self):
		form = self._complete()
		trainer2 = self._user("eff_trainer2@example.com", "Eff", "Trainer2", ["LMS Trainer"])
		with patch("frappe.sendmail"):
			ef.sync_assignment_trainers_to_feedback(self.batch.name, [self.trainer.name, trainer2.name])
		form.reload()
		self._schedule_spaced(form)
		form.reload()
		self.assertTrue(form.sessions_scheduled)
		# Remove trainer2 (unrecorded) — row dropped, form stays scheduled.
		with patch("frappe.sendmail"):
			ef.sync_assignment_trainers_to_feedback(self.batch.name, [self.trainer.name])
		form.reload()
		self.assertEqual({r.trainer for r in form.trainer_feedback}, {self.trainer.name})
		self.assertTrue(form.sessions_scheduled)

	def test_remove_recorded_trainer_is_kept(self):
		form = self._complete()
		self._schedule(form)
		self._as(self.trainer.name, ef.save_trainer_feedback, form.name, "Mock done.")
		with patch("frappe.sendmail"):
			ef.sync_assignment_trainers_to_feedback(self.batch.name, [])  # remove all
		form.reload()
		# Trainer already recorded → kept despite removal from the assignment.
		self.assertEqual({r.trainer for r in form.trainer_feedback}, {self.trainer.name})

	def test_update_assignment_trainers_updates_batch_and_form(self):
		form = self._complete()
		trainer2 = self._user("eff_trainer2@example.com", "Eff", "Trainer2", ["LMS Trainer"])
		with patch("frappe.sendmail"):
			self._as(
				self.master.name,
				ca.update_assignment_trainers,
				self.batch.name,
				[self.trainer.name, trainer2.name],
			)
		instructors = set(
			frappe.get_all(
				"Course Instructor",
				{"parent": self.batch.name, "parenttype": "LMS Batch"},
				pluck="instructor",
			)
		)
		self.assertEqual(instructors, {self.trainer.name, trainer2.name})
		form.reload()
		self.assertEqual(
			{r.trainer for r in form.trainer_feedback}, {self.trainer.name, trainer2.name}
		)

	# ── manager sync ──────────────────────────────────────────────────────────
	def _other_manager(self):
		u = self._user("eff_mgr2@example.com", "Eff", "Mgr2", ["LMS Manager"])
		return self._employee(u.name, "Eff Manager2")

	def test_manager_change_updates_when_no_manager_feedback(self):
		form = self._complete()
		self._schedule(form)
		new_emp = self._other_manager()
		# Mirror the real flow: Employee.reports_to is set first, then the sync runs.
		frappe.db.set_value("Employee", self.emp_learner, "reports_to", new_emp)
		with patch("frappe.sendmail"):
			ef.sync_manager_to_feedback(self.emp_learner, new_emp)
		form.reload()
		self.assertEqual(form.immediate_manager, new_emp)

	def test_manager_change_skipped_when_manager_feedback_recorded(self):
		form = self._complete()
		self._schedule(form)
		form.reload()
		self._as(
			self.manager.name,
			ef.save_manager_feedback,
			form.name,
			"Manager note.",
			form.manager_sessions[0].name,
		)
		new_emp = self._other_manager()
		frappe.db.set_value("Employee", self.emp_learner, "reports_to", new_emp)
		ef.sync_manager_to_feedback(self.emp_learner, new_emp)
		form.reload()
		self.assertEqual(form.immediate_manager, self.emp_manager)  # unchanged

	def test_manager_removed_clears_sessions(self):
		form = self._complete()
		self._schedule(form)
		frappe.db.set_value("Employee", self.emp_learner, "reports_to", None)
		ef.sync_manager_to_feedback(self.emp_learner, None)
		form.reload()
		self.assertFalse(form.immediate_manager)
		self.assertEqual(len(form.manager_sessions), 0)
