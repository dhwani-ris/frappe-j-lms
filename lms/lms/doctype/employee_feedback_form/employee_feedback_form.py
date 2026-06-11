# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime, strip_html


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
		status: DF.Literal["Draft", "Manager Feedback Added", "Trainer Feedback Added", "Completed"]
		trainer_feedback: DF.Table[EmployeeFeedbackTrainer]
	# end: auto-generated types

	def validate(self):
		before = self.get_doc_before_save()

		# A completed form is locked. Only an explicit reopen (L&D Admin / HR) may edit it.
		if before and before.status == "Completed" and not self.flags.get("reopening"):
			frappe.throw(
				_("This feedback form is completed. Ask an L&D Admin to reopen it before editing.")
			)

		self.set_feedback_flags(before)

		if self.flags.get("reopening"):
			self.status = "Draft"
		elif self.flags.get("allow_complete"):
			self.validate_completion()
			self.status = "Completed"
		else:
			self.compute_status()

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

	def all_trainers_recorded(self):
		return bool(self.trainer_feedback) and all(cint(r.recorded) for r in self.trainer_feedback)

	def compute_status(self):
		"""Derive the furthest non-terminal state. 'Completed' is only ever set by the
		explicit complete action, never here."""
		manager_ok = cint(self.manager_feedback_done)
		if manager_ok and self.all_trainers_recorded():
			self.status = "Trainer Feedback Added"
		elif manager_ok:
			self.status = "Manager Feedback Added"
		else:
			self.status = "Draft"

	def validate_completion(self):
		"""Gate the final completion: manager + at least one trainer (all recorded) + master."""
		if (
			not cint(self.manager_feedback_done)
			or not self.all_trainers_recorded()
			or not cint(self.master_feedback_done)
		):
			frappe.throw(
				_("Manager, all trainer, and master trainer feedback must be completed before submitting.")
			)
