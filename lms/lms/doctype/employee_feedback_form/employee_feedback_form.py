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
		manager_feedback: DF.TextEditor | None
		manager_feedback_by: DF.Link | None
		manager_feedback_done: DF.Check
		manager_feedback_on: DF.Datetime | None
		manager_meeting_datetime: DF.Datetime | None
		master_feedback: DF.TextEditor | None
		master_feedback_by: DF.Link | None
		master_feedback_done: DF.Check
		master_feedback_on: DF.Datetime | None
		master_meeting_datetime: DF.Datetime | None
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

		self.set_feedback_flags(before)

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
		"""The meeting slots in their required chronological order:
		manager (if any) → each trainer row in order → master trainer."""
		slots = []
		if self.immediate_manager:
			slots.append((_("Manager"), self.manager_meeting_datetime))
		for idx, row in enumerate(self.trainer_feedback, start=1):
			label = row.trainer_name or row.trainer or _("Trainer {0}").format(idx)
			slots.append((label, row.meeting_datetime))
		slots.append((_("Master Trainer"), self.master_meeting_datetime))
		return slots

	def validate_schedule(self):
		"""All meeting times must be present, in the future, in strict order
		(manager < trainers in row order < master) and ≥15 minutes apart."""
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

		if norm(self.manager_meeting_datetime) != norm(before.manager_meeting_datetime):
			return True
		if norm(self.master_meeting_datetime) != norm(before.master_meeting_datetime):
			return True
		before_rows = {r.name: r.meeting_datetime for r in before.trainer_feedback}
		for row in self.trainer_feedback:
			if norm(row.meeting_datetime) != norm(before_rows.get(row.name)):
				return True
		return False

	# -- feedback flags & status --------------------------------------------

	def set_feedback_flags(self, before=None):
		"""Mark each block (manager / master / every trainer row) as recorded once its
		meeting date and feedback text are both present, and stamp who recorded it."""
		# Manager block
		self.manager_feedback_done = (
			1 if (self.manager_meeting_datetime and _has_text(self.manager_feedback)) else 0
		)
		self._stamp_reviewer(
			"manager_feedback_done", "manager_feedback_by", "manager_feedback_on", before
		)

		# Master trainer block
		self.master_feedback_done = (
			1 if (self.master_meeting_datetime and _has_text(self.master_feedback)) else 0
		)
		self._stamp_reviewer(
			"master_feedback_done", "master_feedback_by", "master_feedback_on", before
		)

		# Each trainer row
		for row in self.trainer_feedback:
			row.recorded = 1 if (row.meeting_datetime and _has_text(row.feedback)) else 0

	def _stamp_reviewer(self, done_field, by_field, on_field, before=None):
		done = cint(self.get(done_field))
		prev_done = cint(before.get(done_field)) if before else 0
		if done and not prev_done:
			self.set(by_field, frappe.session.user)
			self.set(on_field, now_datetime())
		elif not done:
			self.set(by_field, None)
			self.set(on_field, None)

	def manager_required(self):
		return bool(self.immediate_manager)

	def manager_ok(self):
		return (not self.manager_required()) or cint(self.manager_feedback_done)

	def all_trainers_recorded(self):
		return bool(self.trainer_feedback) and all(cint(r.recorded) for r in self.trainer_feedback)

	def compute_status(self):
		"""Status reflects progress. Feedback only opens after the Master Trainer has
		scheduled all sessions; 'Completed' is set only by the explicit complete action."""
		if not cint(self.sessions_scheduled):
			self.status = "Draft"
			return
		if self.manager_ok() and self.all_trainers_recorded():
			self.status = "Trainer Feedback Added"
		elif cint(self.manager_feedback_done):
			self.status = "Manager Feedback Added"
		else:
			self.status = "Sessions Scheduled"

	def validate_completion(self):
		"""Gate the final completion: manager (if any) + at least one trainer (all
		recorded) + master trainer feedback."""
		if (
			not self.manager_ok()
			or not self.all_trainers_recorded()
			or not cint(self.master_feedback_done)
		):
			frappe.throw(
				_("Manager, all trainer, and master trainer feedback must be completed before submitting.")
			)
