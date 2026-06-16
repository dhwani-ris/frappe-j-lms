# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, now_datetime, strip_html

SESSION_GAP_MINUTES = 15
SESSION_GAP_SECONDS = SESSION_GAP_MINUTES * 60


def _has_text(value):
	"""True when a rich-text / text field holds real content (not just empty markup)."""
	if not value:
		return False
	return bool(strip_html(value).strip())


class EmployeeFeedbackForm(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from lms.lms.doctype.employee_feedback_session.employee_feedback_session import (
			EmployeeFeedbackSession,
		)
		from lms.lms.doctype.employee_feedback_trainer.employee_feedback_trainer import (
			EmployeeFeedbackTrainer,
		)

		batch: DF.Link | None
		completed_on: DF.Date | None
		course: DF.Link
		course_title: DF.Data | None
		employee: DF.Link
		employee_name: DF.Data | None
		immediate_manager: DF.Link | None
		manager_sessions: DF.Table[EmployeeFeedbackSession]
		master_sessions: DF.Table[EmployeeFeedbackSession]
		master_trainer: DF.Link | None
		sessions_scheduled: DF.Check
		status: DF.Literal[
			"Draft",
			"Sessions Scheduled",
			"Manager Feedback Added",
			"Trainer Feedback Added",
			"Completed",
		]
		trainer_feedback: DF.Table[EmployeeFeedbackTrainer]
	# end: auto-generated types

	def validate(self):
		before = self.get_doc_before_save()

		# A completed form is locked. Only an explicit reopen (L&D Admin / HR) may edit it.
		if before and before.status == "Completed" and not self.flags.get("reopening"):
			frappe.throw(
				_("This feedback form is completed. Ask an L&D Admin to reopen it before editing.")
			)

		# Meeting times are owned by the Master Trainer and locked once scheduled. Nobody
		# may change them through a normal save — only an explicit (re)schedule.
		if (
			before
			and cint(before.sessions_scheduled)
			and not self.flags.get("scheduling")
			and not self.flags.get("rescheduling")
			and self._meeting_times_changed(before)
		):
			frappe.throw(
				_("Meeting times are locked. Reschedule the sessions to change them.")
			)

		if self.flags.get("scheduling"):
			self.validate_schedule()
			self.sessions_scheduled = 1

		self.set_session_flags(before)

		if self.flags.get("reopening") or self.flags.get("rescheduling"):
			self.sessions_scheduled = 0
			self.status = "Draft"
		elif self.flags.get("allow_complete"):
			self.validate_completion()
			self.status = "Completed"
		else:
			self.compute_status()

	# -- scheduling ----------------------------------------------------------

	def _ordered_slots(self):
		"""Meeting slots in required chronological order: all manager sessions (in row
		order) → each trainer row → all master sessions (in row order)."""
		slots = []
		if self.immediate_manager:
			for idx, row in enumerate(self.manager_sessions, start=1):
				slots.append((_("Manager session {0}").format(idx), row.meeting_datetime))
		for idx, row in enumerate(self.trainer_feedback, start=1):
			label = row.trainer_name or row.trainer or _("Trainer {0}").format(idx)
			slots.append((label, row.meeting_datetime))
		for idx, row in enumerate(self.master_sessions, start=1):
			slots.append((_("Master session {0}").format(idx), row.meeting_datetime))
		return slots

	def validate_schedule(self):
		"""All meeting times present, in the future, in strict group order
		(all manager < all trainers < all master, each group in row order) and
		≥15 minutes apart. At least one manager session (when the employee has a
		manager) and one master session are required."""
		if self.immediate_manager and not self.manager_sessions:
			frappe.throw(_("Add at least one manager feedback session before scheduling."))
		if not self.master_sessions:
			frappe.throw(_("Add at least one master trainer feedback session before scheduling."))

		slots = self._ordered_slots()
		for label, dt in slots:
			if not dt:
				frappe.throw(
					_("A meeting time is required for {0} before confirming the schedule.").format(label)
				)

		now = now_datetime()
		parsed = [(label, get_datetime(dt)) for label, dt in slots]

		for label, dt in parsed:
			if dt <= now:
				frappe.throw(_("Meeting time for {0} must be in the future.").format(label))

		for (plabel, pdt), (clabel, cdt) in zip(parsed, parsed[1:]):
			if cdt <= pdt:
				frappe.throw(
					_("{0}'s meeting must be scheduled before {1}'s meeting.").format(plabel, clabel)
				)
			if (cdt - pdt).total_seconds() < SESSION_GAP_SECONDS:
				frappe.throw(
					_("There must be at least {0} minutes between {1}'s and {2}'s meetings.").format(
						SESSION_GAP_MINUTES, plabel, clabel
					)
				)

	def _meeting_times_changed(self, before):
		def norm(v):
			return str(v or "")

		def snapshot(doc):
			snap = {}
			for r in doc.manager_sessions:
				snap[("m", r.name)] = norm(r.meeting_datetime)
			for r in doc.master_sessions:
				snap[("x", r.name)] = norm(r.meeting_datetime)
			for r in doc.trainer_feedback:
				snap[("t", r.name)] = norm(r.meeting_datetime)
			return snap

		return snapshot(self) != snapshot(before)

	# -- feedback flags & status --------------------------------------------

	def set_session_flags(self, before=None):
		"""Mark each session/row as recorded once its meeting date + feedback text are
		both present, and stamp who recorded it (on the 0→1 edge)."""
		prev = {}
		if before:
			for r in list(before.manager_sessions) + list(before.master_sessions):
				prev[r.name] = cint(r.recorded)

		for row in list(self.manager_sessions) + list(self.master_sessions):
			recorded = 1 if (row.meeting_datetime and _has_text(row.feedback)) else 0
			row.recorded = recorded
			if recorded and not prev.get(row.name, 0):
				row.recorded_by = frappe.session.user
				row.recorded_on = now_datetime()
			elif not recorded:
				row.recorded_by = None
				row.recorded_on = None

		for row in self.trainer_feedback:
			row.recorded = 1 if (row.meeting_datetime and _has_text(row.feedback)) else 0

	def manager_required(self):
		return bool(self.immediate_manager)

	def manager_done(self):
		if not self.manager_required():
			return True
		return bool(self.manager_sessions) and all(cint(r.recorded) for r in self.manager_sessions)

	def master_done(self):
		return bool(self.master_sessions) and all(cint(r.recorded) for r in self.master_sessions)

	def all_trainers_recorded(self):
		return bool(self.trainer_feedback) and all(cint(r.recorded) for r in self.trainer_feedback)

	def compute_status(self):
		"""Status reflects progress. Feedback opens only after the Master Trainer has
		scheduled all sessions; 'Completed' is set only by the explicit complete action."""
		if not cint(self.sessions_scheduled):
			self.status = "Draft"
			return
		manager_done = self.manager_done()
		if manager_done and self.all_trainers_recorded():
			self.status = "Trainer Feedback Added"
		elif self.immediate_manager and manager_done:
			self.status = "Manager Feedback Added"
		else:
			self.status = "Sessions Scheduled"

	def validate_completion(self):
		"""Gate the final completion: every manager session (if any) + every trainer
		row + every master session recorded."""
		if not (self.manager_done() and self.all_trainers_recorded() and self.master_done()):
			frappe.throw(
				_("Manager, all trainer, and master trainer feedback must be completed before submitting.")
			)
