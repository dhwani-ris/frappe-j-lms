from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from lms.lms.custom.notifications import (
	HR_ROLE,
	MASTER_TRAINER_ROLE_PROFILE,
)


class TestEmployeeExitNotifications(FrappeTestCase):
	"""Tests for the employee exit / access revocation notifications.

	Invariant under test: whenever an employee leaves the organisation
	(Employee.status -> Left) or their LMS access is revoked (Employee.status ->
	Inactive/Suspended, the linked User disabled, or the LMS role profile
	removed), HR, the immediate manager and the master trainer(s) each receive
	an in-app notification AND an email. The exiting employee is never notified
	about their own exit, and unrelated edits produce nothing.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.company = self._get_company()

		self.hr = self._user("ex_hr@example.com", "Exit", "HR", [HR_ROLE])
		self.manager = self._user("ex_manager@example.com", "Exit", "Manager", ["LMS Manager"])
		self.master = self._master_trainer("ex_master@example.com", "Exit", "Master")
		self.leaver = self._user("ex_leaver@example.com", "Exit", "Leaver", ["LMS Student"])

		# Employee reporting line: leaver -> manager.
		self.manager_emp = self._employee(self.manager.name, "Exit Manager")
		self.leaver_emp = self._employee(
			self.leaver.name, "Exit Leaver", reports_to=self.manager_emp
		)

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
				"company_name": "Exit Test Co",
				"abbr": "ETC",
				"default_currency": "INR",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		return doc.name

	def _user(self, email, first, last, roles):
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			user.enabled = 1
			existing_roles = {r.role for r in user.roles}
			for role in roles:
				if role not in existing_roles:
					user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
			return user
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
			frappe.db.set_value(
				"Employee", existing, {"status": "Active", "reports_to": reports_to}
			)
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

	def _clear_logs(self):
		frappe.db.delete("Notification Log", {"document_name": self.leaver_emp})

	def _stakeholders(self):
		return [self.hr.name, self.manager.name, self.master.name]

	def _logs_for(self, user):
		return frappe.get_all(
			"Notification Log",
			{"for_user": user, "document_name": self.leaver_emp},
			pluck="subject",
		)

	def _emailed_recipients(self, mock_sendmail):
		"""Recipients emailed *about our employee*. Scope by reference_name
		because HR/master trainers are org-wide."""
		emailed = set()
		for call in mock_sendmail.call_args_list:
			if call.kwargs.get("reference_name") == self.leaver_emp:
				emailed.update(call.kwargs.get("recipients", []))
		return emailed

	def _set_status(self, status, relieving_date=None):
		emp = frappe.get_doc("Employee", self.leaver_emp)
		emp.status = status
		if relieving_date:
			emp.relieving_date = relieving_date
		emp.save(ignore_permissions=True)

	# ── tests ────────────────────────────────────────────────────────────────
	def test_employee_left_notifies_hr_manager_and_master_trainer(self):
		with patch("frappe.sendmail") as mock_sendmail:
			self._set_status("Left", relieving_date=nowdate())

		for user in self._stakeholders():
			logs = self._logs_for(user)
			self.assertEqual(len(logs), 1, f"expected exactly one notification for {user}")
			self.assertIn("has left the organization", logs[0])

		emailed = self._emailed_recipients(mock_sendmail)
		for user in self._stakeholders():
			self.assertIn(user, emailed, f"expected an email to {user}")

		# The exiting employee is never notified about their own exit.
		self.assertEqual(self._logs_for(self.leaver.name), [])
		self.assertNotIn(self.leaver.name, emailed)

	def test_employee_inactive_sends_access_revoked(self):
		with patch("frappe.sendmail") as mock_sendmail:
			self._set_status("Inactive")

		for user in self._stakeholders():
			logs = self._logs_for(user)
			self.assertEqual(len(logs), 1, f"expected exactly one notification for {user}")
			self.assertIn("Access Revoked", logs[0])

		emailed = self._emailed_recipients(mock_sendmail)
		for user in self._stakeholders():
			self.assertIn(user, emailed, f"expected an email to {user}")

	def test_unrelated_employee_edit_sends_nothing(self):
		with patch("frappe.sendmail") as mock_sendmail:
			emp = frappe.get_doc("Employee", self.leaver_emp)
			emp.employee_name = "Exit Leaver Renamed"
			emp.save(ignore_permissions=True)

		for user in self._stakeholders():
			self.assertEqual(self._logs_for(user), [])
		self.assertEqual(self._emailed_recipients(mock_sendmail), set())

	def test_disabling_user_directly_sends_access_revoked(self):
		with patch("frappe.sendmail") as mock_sendmail:
			user = frappe.get_doc("User", self.leaver.name)
			user.enabled = 0
			user.save(ignore_permissions=True)

		for stakeholder in self._stakeholders():
			logs = self._logs_for(stakeholder)
			self.assertEqual(
				len(logs), 1, f"expected exactly one notification for {stakeholder}"
			)
			self.assertIn("Access Revoked", logs[0])

		emailed = self._emailed_recipients(mock_sendmail)
		for stakeholder in self._stakeholders():
			self.assertIn(stakeholder, emailed, f"expected an email to {stakeholder}")

	def test_disabling_user_of_exited_employee_does_not_double_notify(self):
		# Employee already Left (set silently, bypassing hooks) — disabling the
		# user afterwards must not produce a second notification.
		frappe.db.set_value(
			"Employee",
			self.leaver_emp,
			{"status": "Left", "relieving_date": nowdate()},
		)
		self._clear_logs()

		with patch("frappe.sendmail") as mock_sendmail:
			user = frappe.get_doc("User", self.leaver.name)
			user.enabled = 0
			user.save(ignore_permissions=True)

		for stakeholder in self._stakeholders():
			self.assertEqual(self._logs_for(stakeholder), [])
		self.assertEqual(self._emailed_recipients(mock_sendmail), set())

	def test_unassign_role_profile_sends_access_revoked(self):
		from lms.lms.custom.dashboard_api import unassign_employee_role

		# Give the leaver a role profile that HR can revoke.
		frappe.db.set_value(
			"User", self.leaver.name, "role_profile_name", MASTER_TRAINER_ROLE_PROFILE
		)
		self._clear_logs()

		with patch("frappe.sendmail") as mock_sendmail:
			unassign_employee_role(self.leaver_emp)

		for user in self._stakeholders():
			logs = self._logs_for(user)
			self.assertEqual(len(logs), 1, f"expected exactly one notification for {user}")
			self.assertIn("Access Revoked", logs[0])

		emailed = self._emailed_recipients(mock_sendmail)
		for user in self._stakeholders():
			self.assertIn(user, emailed, f"expected an email to {user}")
