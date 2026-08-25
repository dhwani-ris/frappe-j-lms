"""Backfill Employee Feedback Forms for enrollments that already reached 100% before the
auto-creation hook (``create_feedback_form_on_completion``) existed.

Delegates to ``backfill_feedback_forms``, which reuses the live eligibility rules (assigned
active employee + assignment micro-batch, one form per employee + course) and is therefore
safe to re-run. We send notifications so the responsible managers / trainers / master
trainers are prompted to act on the historical forms.

Runs once via the patch log; the underlying backfill is itself idempotent.
"""

import frappe

from lms.lms.custom.employee_feedback import DOCTYPE, backfill_feedback_forms


def execute():
	if not frappe.db.table_exists(DOCTYPE):
		return  # Employee Feedback Form not installed on this site yet

	result = backfill_feedback_forms(send_notifications=1)
	print(
		"Employee Feedback backfill: "
		f"scanned {result['scanned_completed_enrollments']} completed enrollment(s), "
		f"{result['eligible']} eligible, created {result['created']} form(s)"
	)
