# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Calendar sync for the Employee Feedback Form.

Each scheduled feedback session (manager / each trainer / master) is mirrored as a Frappe
``Event`` that invites the reviewer + the employee. When the event's ``google_calendar`` is
a connected account with push enabled, Frappe's built-in Event → Google Calendar sync emails
a real invite to every attendee (any provider). The scheduling Master Trainer's own connected
calendar is preferred so the MT is the organiser.

``sync_feedback_calendar(form)`` is an idempotent reconcile keyed by ``custom_feedback_key``
(back-linked via ``custom_feedback_form`` on Event): it creates new session events, updates
changed ones in place, and cancels (deletes) ones that no longer exist — so reschedules
update and removals/unscheduling cancel. It is fully guarded: a calendar/Google failure is
logged and never breaks the feedback flow.
"""

import frappe
from frappe.utils import add_to_date, get_datetime

DOCTYPE = "Employee Feedback Form"
SESSION_MINUTES = 15


def _employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") if employee else None


def _resolve_google_calendar(master_trainer):
	"""Prefer the scheduling MT's connected, push-enabled calendar (so the MT organises);
	else fall back to any push-enabled calendar as the site default. None => sync off."""
	if master_trainer:
		gc = frappe.db.get_value(
			"Google Calendar",
			{"user": master_trainer, "push_to_google_calendar": 1, "enable": 1},
			"name",
		)
		if gc:
			return gc
	return frappe.db.get_value(
		"Google Calendar", {"push_to_google_calendar": 1, "enable": 1}, "name"
	)


def _desired_sessions(form):
	"""[(key, start, end, reviewer_user, role)] for every scheduled session with a time."""
	manager_user = _employee_user(form.immediate_manager) if form.immediate_manager else None
	out = []

	if form.immediate_manager and manager_user:
		for idx, row in enumerate(form.manager_sessions):
			if row.meeting_datetime:
				out.append((f"manager:{idx}", row.meeting_datetime, manager_user, "Manager"))

	for row in form.trainer_feedback:
		if row.meeting_datetime and row.trainer:
			out.append((f"trainer:{row.trainer}", row.meeting_datetime, row.trainer, "Trainer"))

	if form.master_trainer:
		for idx, row in enumerate(form.master_sessions):
			if row.meeting_datetime:
				out.append((f"master:{idx}", row.meeting_datetime, form.master_trainer, "Master Trainer"))

	sessions = []
	for key, dt, reviewer, role in out:
		start = get_datetime(dt)
		sessions.append(
			{
				"key": key,
				"start": start,
				"end": add_to_date(start, minutes=SESSION_MINUTES),
				"reviewer": reviewer,
				"role": role,
			}
		)
	return sessions


def _participant_rows(reviewer_user, employee_user):
	"""Event Participants for the reviewer + employee. A Frappe User's name *is* the email,
	so the email used by Google's get_attendees() is the user id itself."""
	rows = []
	for user in dict.fromkeys([reviewer_user, employee_user]):  # de-dupe, keep order
		if user:
			rows.append({"reference_doctype": "User", "reference_docname": user, "email": user})
	return rows


def sync_feedback_calendar(form):
	"""Entry point — never raises; a calendar failure must not break scheduling."""
	try:
		_sync(form)
	except Exception:
		frappe.log_error(title="Employee Feedback calendar sync failed")


def _sync(form):
	existing = {
		e.custom_feedback_key: e.name
		for e in frappe.get_all(
			"Event",
			filters={"custom_feedback_form": form.name},
			fields=["name", "custom_feedback_key"],
		)
		if e.custom_feedback_key
	}

	# Unscheduled (Draft / reopened) → cancel everything for this form.
	if not form.sessions_scheduled:
		for event_name in existing.values():
			_safe_delete(event_name)
		return

	gcal = _resolve_google_calendar(form.master_trainer)
	employee_user = _employee_user(form.employee)
	employee_name = form.employee_name or frappe.db.get_value("Employee", form.employee, "employee_name")
	course_title = form.course_title or frappe.db.get_value("LMS Course", form.course, "title")

	for s in _desired_sessions(form):
		if not s["reviewer"]:
			continue
		subject = f"Feedback: {employee_name} — {s['role']} ({course_title})"
		participants = _participant_rows(s["reviewer"], employee_user)
		event_name = existing.pop(s["key"], None)
		if event_name:
			_safe_update(event_name, subject, s, participants, gcal)
		else:
			_safe_create(form.name, s, subject, participants, gcal)

	# Sessions that disappeared (trainer removed, fewer manager/master sessions) → cancel.
	for event_name in existing.values():
		_safe_delete(event_name)


def _safe_create(form_name, session, subject, participants, gcal):
	try:
		ev = frappe.new_doc("Event")
		ev.subject = subject
		ev.event_type = "Private"
		ev.starts_on = session["start"]
		ev.ends_on = session["end"]
		ev.add_video_conferencing = 0
		ev.custom_feedback_form = form_name
		ev.custom_feedback_key = session["key"]
		if gcal:
			ev.sync_with_google_calendar = 1
			ev.google_calendar = gcal
		for row in participants:
			ev.append("event_participants", row)
		ev.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Employee Feedback calendar: create event failed")


def _safe_update(event_name, subject, session, participants, gcal):
	try:
		ev = frappe.get_doc("Event", event_name)
		ev.subject = subject
		ev.starts_on = session["start"]
		ev.ends_on = session["end"]
		ev.set("event_participants", participants)
		if gcal and not ev.sync_with_google_calendar:
			ev.sync_with_google_calendar = 1
			ev.google_calendar = gcal
		ev.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Employee Feedback calendar: update event failed")


def _safe_delete(event_name):
	try:
		frappe.delete_doc("Event", event_name, ignore_permissions=True, delete_permanently=False)
	except Exception:
		frappe.log_error(title="Employee Feedback calendar: cancel event failed")
