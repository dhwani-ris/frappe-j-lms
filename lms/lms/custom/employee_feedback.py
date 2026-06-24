# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Employee Feedback Form — backend.

A feedback form is auto-created when an employee completes a course 100%. The
immediate manager and (org-wide) master trainer each record feedback once; every
assigned trainer records feedback through a child table. Once the manager, all
trainers and a master trainer are done, a master trainer marks the form Completed.

Course completion, the assignment micro-batch and the stakeholder model all reuse
existing Jamboree primitives — see ``course_assignment.py`` and ``notifications.py``.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, format_datetime, get_datetime, getdate, today
from frappe.utils.user import get_users_with_role

from lms.lms.custom.feedback_calendar import sync_feedback_calendar
from lms.lms.custom.notifications import (
	HR_ROLE,
	_get_master_trainers,
	_notify,
	notify_feedback_scheduled,
)

DOCTYPE = "Employee Feedback Form"
MASTER_TRAINER_ROLE = "LMS Master Trainer"
SESSION_GAP_SECONDS = 15 * 60  # overlapping 15-min blocks ⇒ conflict


# ---------------------------------------------------------------------------
# Small resolution helpers
# ---------------------------------------------------------------------------


def _clean(value):
	"""Normalise empty strings coming from the portal into ``None``."""
	if value in ("", "null", "undefined"):
		return None
	return value


def _employee_for_user(user, active_only=False):
	filters = {"user_id": user}
	if active_only:
		filters["status"] = "Active"
	return frappe.db.get_value("Employee", filters, "name")


def _employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") if employee else None


def _manager_user(form):
	return _employee_user(form.immediate_manager) if form.immediate_manager else None


def _resolve_micro_batch(member, course):
	"""The assignment batch for this employee + course: a batch the member is enrolled
	in (``LMS Batch Enrollment``) that carries the course (``Batch Course``)."""
	batches = frappe.get_all("LMS Batch Enrollment", {"member": member}, pluck="batch")
	for batch in batches:
		if frappe.db.exists(
			"Batch Course", {"parent": batch, "parenttype": "LMS Batch", "course": course}
		):
			return batch
	return None


def is_master_trainer(user):
	return MASTER_TRAINER_ROLE in frappe.get_roles(user)


def _is_admin(user):
	"""L&D Admin: System Manager / LMS HR (the roles that own and reopen forms)."""
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return "System Manager" in roles or HR_ROLE in roles


def _is_super(user):
	"""Users who may see every form: admins + org-wide master trainers."""
	return _is_admin(user) or is_master_trainer(user)


def can_schedule(user=None):
	"""Who may schedule / reschedule feedback sessions: any Master Trainer + admins."""
	user = user or frappe.session.user
	return is_master_trainer(user) or _is_admin(user)


def can_act_master(form, user=None):
	"""Who may record master feedback / complete: the form's assigned master trainer
	(the MT who scheduled) or an admin."""
	user = user or frappe.session.user
	return _is_admin(user) or (bool(form.master_trainer) and form.master_trainer == user)


def ready_to_complete(form):
	return bool(form.manager_done() and form.master_done() and form.all_trainers_recorded())


def can_edit_manager(form, user=None):
	user = user or frappe.session.user
	return _is_admin(user) or _manager_user(form) == user


def _require_scheduled(form):
	if not cint(form.sessions_scheduled):
		frappe.throw(
			_("Feedback can be recorded only after the sessions are scheduled."),
			frappe.ValidationError,
		)


def _active_forms_excluding(extra_filters, exclude_form):
	"""Names of not-Completed forms matching ``extra_filters``, excluding this one."""
	filters = {"name": ["!=", exclude_form], "status": ["!=", "Completed"]}
	filters.update(extra_filters)
	return frappe.get_all(DOCTYPE, filters=filters, pluck="name")


def _session_times(form_names, parentfield):
	"""All ``meeting_datetime`` values of the given session rows on the given forms."""
	if not form_names:
		return []
	return frappe.get_all(
		"Employee Feedback Session",
		filters={
			"parenttype": DOCTYPE,
			"parentfield": parentfield,
			"parent": ["in", form_names],
			"meeting_datetime": ["is", "set"],
		},
		pluck="meeting_datetime",
	)


def _busy_blocks(user, exclude_form):
	"""All scheduled meeting times for ``user`` across *other, not-Completed* forms —
	their manager sessions (forms they manage), their trainer-row slots, and their
	master sessions (forms where they are the master trainer)."""
	blocks = []

	emps = frappe.get_all("Employee", {"user_id": user}, pluck="name")
	if emps:
		mgr_forms = _active_forms_excluding({"immediate_manager": ["in", emps]}, exclude_form)
		blocks += _session_times(mgr_forms, "manager_sessions")

	master_forms = _active_forms_excluding({"master_trainer": user}, exclude_form)
	blocks += _session_times(master_forms, "master_sessions")

	trainer_rows = frappe.get_all(
		"Employee Feedback Trainer",
		{"trainer": user, "parenttype": DOCTYPE},
		["parent", "meeting_datetime"],
	)
	parents = [r.parent for r in trainer_rows if r.parent != exclude_form and r.meeting_datetime]
	statuses = (
		dict(frappe.get_all(DOCTYPE, {"name": ["in", parents]}, ["name", "status"], as_list=True))
		if parents
		else {}
	)
	for r in trainer_rows:
		if (
			r.parent != exclude_form
			and r.meeting_datetime
			and statuses.get(r.parent) != "Completed"
		):
			blocks.append(r.meeting_datetime)

	return [b for b in blocks if b]


def _check_conflicts(form, scheduler_user):
	"""Reject if any participant's proposed 15-min block overlaps a block they already
	have on another active form."""
	participants = []
	if form.immediate_manager:
		mu = _manager_user(form)
		if mu:
			for row in form.manager_sessions:
				participants.append((_("The manager"), mu, row.meeting_datetime))
	for row in form.trainer_feedback:
		if row.trainer:
			label = row.trainer_name or row.trainer
			participants.append((label, row.trainer, row.meeting_datetime))
	for row in form.master_sessions:
		participants.append((_("The master trainer"), scheduler_user, row.meeting_datetime))

	for label, user, dt in participants:
		if not dt:
			continue
		cand = get_datetime(dt)
		for block in _busy_blocks(user, form.name):
			if abs((get_datetime(block) - cand).total_seconds()) < SESSION_GAP_SECONDS:
				frappe.throw(
					_("{0} already has a feedback session scheduled around {1}.").format(
						label, frappe.utils.format_datetime(cand)
					)
				)


# ---------------------------------------------------------------------------
# Auto-creation on 100% course completion (LMS Enrollment.on_update)
# ---------------------------------------------------------------------------


def _eligible_for_feedback(member, course):
	"""A form is created only for an *assigned* active employee (a micro-batch carries the
	course) and only once per employee + course. Returns (employee, batch) or None."""
	employee = _employee_for_user(member, active_only=True)
	if not employee:
		return None  # only employees get an Employee Feedback Form
	batch = _resolve_micro_batch(member, course)
	if not batch:
		return None  # only courses assigned via the assign-course flow (batch + trainers)
	if frappe.db.exists(DOCTYPE, {"employee": employee, "course": course}):
		return None  # one form per employee + course
	return employee, batch


def _create_feedback_form(employee, course, batch, completed_on=None, notify=True):
	"""Create the Draft form + pre-fill trainer rows from the batch instructors."""
	form = frappe.new_doc(DOCTYPE)
	form.employee = employee
	form.course = course
	form.batch = batch
	form.completed_on = completed_on or today()
	form.status = "Draft"

	instructors = frappe.get_all(
		"Course Instructor",
		{"parent": batch, "parenttype": "LMS Batch"},
		pluck="instructor",
	)
	for trainer in instructors:
		form.append("trainer_feedback", {"trainer": trainer})

	form.insert(ignore_permissions=True)
	if notify:
		notify_form_created(form)
	return form.name


def create_feedback_form_on_completion(doc, method=None):
	"""When an enrolled employee hits 100%, create exactly one feedback form for the
	employee + course — but only for *assigned* employees (those with an assignment
	micro-batch carrying trainers) and only once per employee + course."""
	if cint(doc.progress) < 100:
		return
	eligible = _eligible_for_feedback(doc.member, doc.course)
	if not eligible:
		return
	employee, batch = eligible
	_create_feedback_form(employee, doc.course, batch, notify=True)


@frappe.whitelist()
def backfill_feedback_forms(send_notifications=0, dry_run=0):
	"""One-off backfill: create Employee Feedback Forms for enrollments that already hit
	100% before the auto-creation hook existed. Reuses the same eligibility rules
	(assigned active employee + micro-batch, one per employee + course), so it is safe to
	re-run (idempotent). Historical forms use the enrollment's completion date and, by
	default, send **no** notifications (pass send_notifications=1 to override).

	dry_run=1 reports how many forms *would* be created without writing anything.
	Run as e.g. `bench --site <site> execute lms.lms.custom.employee_feedback.backfill_feedback_forms`."""
	frappe.only_for(["System Manager", "LMS HR"])
	notify = cint(send_notifications)
	dry = cint(dry_run)

	rows = frappe.get_all(
		"LMS Enrollment",
		filters={"progress": [">=", 100]},
		fields=["name", "member", "course", "modified"],
	)

	created, eligible = 0, 0
	for r in rows:
		elig = _eligible_for_feedback(r.member, r.course)
		if not elig:
			continue
		eligible += 1
		if dry:
			continue
		employee, batch = elig
		_create_feedback_form(
			employee, r.course, batch, completed_on=getdate(r.modified), notify=notify
		)
		created += 1
		if created % 50 == 0:
			frappe.db.commit()  # checkpoint so a long backfill isn't one huge transaction

	if not dry:
		frappe.db.commit()

	return {
		"scanned_completed_enrollments": len(rows),
		"eligible": eligible,
		"created": 0 if dry else created,
		"dry_run": bool(dry),
		"notifications_sent": bool(notify) and not dry,
	}


# ---------------------------------------------------------------------------
# Roster sync — keep the feedback form in step with assignment / manager edits
# ---------------------------------------------------------------------------


def sync_assignment_trainers_to_feedback(batch, new_trainers) -> dict:
	"""Reflect an assignment's trainer change in the (non-Completed) feedback form for
	that batch: add new trainer rows; drop removed trainers that have NOT recorded; keep
	removed trainers who already recorded. Adding a trainer to an already-scheduled form
	sends it back to Draft for rescheduling. Returns ``{"unscheduled": bool}``.

	Called only from the role-guarded ``course_assignment.update_assignment_trainers``."""
	if isinstance(new_trainers, str):
		new_trainers = json.loads(new_trainers or "[]")
	new_set = list(dict.fromkeys(new_trainers or []))  # de-dup, keep order

	form_name = frappe.db.get_value(DOCTYPE, {"batch": batch, "status": ["!=", "Completed"]})
	if not form_name:
		return {"unscheduled": False}
	form = frappe.get_doc(DOCTYPE, form_name)

	current = {r.trainer for r in form.trainer_feedback}
	added = [t for t in new_set if t not in current]

	kept, removed = [], []
	for r in form.trainer_feedback:
		if r.trainer in new_set or cint(r.recorded):
			kept.append(r)  # still assigned, or already recorded → keep
		else:
			removed.append(r.trainer)

	if not added and not removed:
		return {"unscheduled": False}

	form.set(
		"trainer_feedback",
		[
			{
				"trainer": r.trainer,
				"meeting_datetime": r.meeting_datetime,
				"feedback": r.feedback,
				"recorded": r.recorded,
			}
			for r in kept
		]
		+ [{"trainer": t} for t in added],
	)

	unscheduled = bool(added) and bool(cint(form.sessions_scheduled))
	if unscheduled:
		form.flags.rescheduling = True  # → Draft, sessions_scheduled = 0
	else:
		form.flags.syncing_roster = True  # keep schedule; bypass the locked-times guard
	# ignore_permissions: caller (update_assignment_trainers) is role-guarded via
	# frappe.only_for(); this is a system-driven roster sync, not a user edit.
	form.save(ignore_permissions=True)

	for trainer in added:
		notify_trainer_added(form, trainer)
	if added:
		_notify_roster_change(form)
	sync_feedback_calendar(form)  # cancel removed trainers' events / cancel all if unscheduled
	return {"unscheduled": unscheduled}


def sync_manager_to_feedback(employee, new_reports_to) -> None:
	"""Reflect a manager change on the employee's non-Completed feedback forms: update
	``immediate_manager`` only while no manager feedback has been recorded; keep the
	scheduled manager session times for the new manager. Removing the manager clears the
	manager sessions.

	Called only from the HR-guarded ``dashboard_api.update_employee_manager``."""
	new_manager = new_reports_to or None
	forms = frappe.get_all(
		DOCTYPE, {"employee": employee, "status": ["!=", "Completed"]}, pluck="name"
	)
	for fname in forms:
		form = frappe.get_doc(DOCTYPE, fname)
		if any(cint(s.recorded) for s in form.manager_sessions):
			continue  # manager feedback already saved — leave it untouched
		if (form.immediate_manager or None) == new_manager:
			continue
		form.immediate_manager = new_manager
		if not new_manager:
			form.set("manager_sessions", [])  # no manager to attend the sessions
		form.flags.syncing_roster = True
		# ignore_permissions: caller (update_employee_manager) is HR-guarded via
		# frappe.only_for(); this is a system-driven roster sync, not a user edit.
		form.save(ignore_permissions=True)
		sync_feedback_calendar(form)  # update manager events' attendee / cancel if removed
		if new_manager:
			notify_manager_assigned(form)


# ---------------------------------------------------------------------------
# Whitelisted reviewer actions (portal + desk)
# ---------------------------------------------------------------------------


def _reconcile_sessions(form, table_field, times):
	"""Rebuild a session table from the scheduler's payload, preserving feedback already
	recorded on rows that are kept (matched by row name)."""
	existing = {r.name: r for r in form.get(table_field)}
	rows = []
	for t in times:
		dt = _clean(t.get("meeting_datetime"))
		rid = t.get("row")
		if rid and rid in existing:
			r = existing[rid]
			rows.append(
				{
					"meeting_datetime": dt,
					"feedback": r.feedback,
					"recorded": r.recorded,
					"recorded_by": r.recorded_by,
					"recorded_on": r.recorded_on,
				}
			)
		else:
			rows.append({"meeting_datetime": dt})
	form.set(table_field, rows)


@frappe.whitelist()
def schedule_sessions(name, manager_times=None, master_times=None, trainer_times=None):
	"""Master-Trainer-only: set every meeting time (manager & master can each have
	multiple sessions), validate order/gap/future + conflicts, self-assign as the form's
	master trainer, and move the form to 'Sessions Scheduled'.

	``manager_times`` / ``master_times`` / ``trainer_times`` are lists of
	``{"row": <existing row name, optional>, "meeting_datetime": ...}``; trainer entries
	may use ``{"trainer": <user>, ...}`` instead of ``row``.
	"""
	form = frappe.get_doc(DOCTYPE, name)
	user = frappe.session.user
	if not can_schedule(user):
		frappe.throw(
			_("Only a master trainer or admin can schedule feedback sessions."),
			frappe.PermissionError,
		)
	if form.status == "Completed":
		frappe.throw(_("Reopen the completed form before scheduling."))

	def _parse(value):
		if isinstance(value, str):
			return json.loads(value or "[]")
		return value or []

	manager_times = _parse(manager_times) if form.immediate_manager else []
	master_times = _parse(master_times)
	trainer_times = _parse(trainer_times)

	_reconcile_sessions(form, "manager_sessions", manager_times)
	_reconcile_sessions(form, "master_sessions", master_times)

	by_row = {t["row"]: _clean(t.get("meeting_datetime")) for t in trainer_times if t.get("row")}
	by_trainer = {
		t["trainer"]: _clean(t.get("meeting_datetime"))
		for t in trainer_times
		if t.get("trainer")
	}
	for row in form.trainer_feedback:
		if row.name in by_row:
			row.meeting_datetime = by_row[row.name]
		elif row.trainer in by_trainer:
			row.meeting_datetime = by_trainer[row.trainer]

	form.master_trainer = user  # scheduler self-assigns (or re-assigns on reschedule)
	_check_conflicts(form, user)

	form.flags.scheduling = True
	form.save(ignore_permissions=True)  # validate_schedule() enforces order/gap/future
	notify_feedback_scheduled(form)
	sync_feedback_calendar(form)
	return _form_payload(form)


@frappe.whitelist()
def reschedule_sessions(name):
	"""Master-Trainer / admin: return a scheduled form to Draft so times can be edited
	again (feedback already entered is preserved). Re-confirming re-notifies everyone."""
	form = frappe.get_doc(DOCTYPE, name)
	if not can_schedule(frappe.session.user):
		frappe.throw(
			_("Only a master trainer or admin can reschedule feedback sessions."),
			frappe.PermissionError,
		)
	if form.status == "Completed":
		frappe.throw(_("Reopen the completed form before rescheduling."))
	form.flags.rescheduling = True
	form.save(ignore_permissions=True)
	sync_feedback_calendar(form)  # unscheduled → cancel the session events
	return _form_payload(form)


def _session_row(form, table_field, row_name):
	if not row_name:
		frappe.throw(_("A feedback session must be selected."))
	row = next((r for r in form.get(table_field) if r.name == row_name), None)
	if not row:
		# Generic message — never echo the client-supplied row name back.
		frappe.throw(_("Invalid or missing feedback session."))
	return row


@frappe.whitelist()
def save_manager_feedback(name, feedback=None, row=None):
	form = frappe.get_doc(DOCTYPE, name)
	if not can_edit_manager(form):
		frappe.throw(
			_("You are not allowed to record manager feedback on this form."),
			frappe.PermissionError,
		)
	_require_scheduled(form)
	_session_row(form, "manager_sessions", row).feedback = _clean(feedback)
	form.save(ignore_permissions=True)
	notify_manager_feedback(form)
	return _form_payload(form)


@frappe.whitelist()
def save_trainer_feedback(name, feedback=None, trainer=None):
	form = frappe.get_doc(DOCTYPE, name)
	user = frappe.session.user
	target = trainer or user

	row = next((r for r in form.trainer_feedback if r.trainer == target), None)
	if not row:
		frappe.throw(_("No trainer row found for {0} on this form.").format(target))

	if not (target == user or _is_admin(user)):
		frappe.throw(
			_("You can only record your own trainer feedback."), frappe.PermissionError
		)

	_require_scheduled(form)
	row.feedback = _clean(feedback)
	form.save(ignore_permissions=True)
	notify_trainer_feedback(form, row.trainer)
	return _form_payload(form)


@frappe.whitelist()
def save_master_feedback(name, feedback=None, row=None):
	form = frappe.get_doc(DOCTYPE, name)
	if not can_act_master(form):
		frappe.throw(
			_("Only the assigned master trainer can record master trainer feedback."),
			frappe.PermissionError,
		)
	_require_scheduled(form)
	_session_row(form, "master_sessions", row).feedback = _clean(feedback)
	form.save(ignore_permissions=True)  # validate() stamps recorded_by = session user
	notify_master_feedback(form)
	return _form_payload(form)


@frappe.whitelist()
def complete_feedback(name):
	form = frappe.get_doc(DOCTYPE, name)
	if not can_act_master(form):
		frappe.throw(
			_("Only the assigned master trainer can complete this feedback form."),
			frappe.PermissionError,
		)
	form.flags.allow_complete = True
	form.save(ignore_permissions=True)  # validate() runs the completion gate and sets Completed
	notify_completed(form)
	return _form_payload(form)


@frappe.whitelist()
def reopen_feedback(name):
	form = frappe.get_doc(DOCTYPE, name)
	if not _is_admin(frappe.session.user):
		frappe.throw(
			_("Only an L&D Admin / HR can reopen a completed feedback form."),
			frappe.PermissionError,
		)
	form.flags.reopening = True
	form.save(ignore_permissions=True)
	sync_feedback_calendar(form)  # back to Draft → cancel the session events
	return _form_payload(form)


# ---------------------------------------------------------------------------
# Whitelisted reads for the portal
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_feedback_form(name):
	form = frappe.get_doc(DOCTYPE, name)
	if not has_permission(form, "read", frappe.session.user):
		frappe.throw(_("You are not permitted to view this feedback form."), frappe.PermissionError)
	return _form_payload(form)


@frappe.whitelist()
def list_my_feedback_forms():
	"""All forms the current user may see (scoped by the permission query), annotated
	with the user's role on each form and whether their action is still pending."""
	user = frappe.session.user
	forms = frappe.get_list(
		DOCTYPE,
		fields=[
			"name",
			"employee",
			"employee_name",
			"course",
			"course_title",
			"status",
			"completed_on",
			"immediate_manager",
			"master_trainer",
			"sessions_scheduled",
			"modified",
		],
		order_by="modified desc",
	)

	my_trainer_parents = set(
		frappe.get_all(
			"Employee Feedback Trainer",
			{"trainer": user, "parenttype": DOCTYPE},
			pluck="parent",
		)
	)
	scheduler = can_schedule(user)

	# Batch the manager lookups (user_id + name) to avoid an N+1 over Employee.
	manager_ids = list({f.immediate_manager for f in forms if f.immediate_manager})
	manager_map = {
		e.name: e
		for e in (
			frappe.get_all(
				"Employee",
				{"name": ["in", manager_ids]},
				["name", "user_id", "employee_name"],
			)
			if manager_ids
			else []
		)
	}

	def _has_unrecorded(form_name, parentfield):
		return bool(
			frappe.db.exists(
				"Employee Feedback Session",
				{"parent": form_name, "parentfield": parentfield, "recorded": 0},
			)
		)

	for f in forms:
		manager = manager_map.get(f.immediate_manager)
		f["is_manager"] = bool(manager) and manager.user_id == user
		f["is_trainer"] = f["name"] in my_trainer_parents
		f["is_master"] = bool(f.master_trainer) and f.master_trainer == user
		f["can_schedule"] = scheduler
		f["immediate_manager_name"] = manager.employee_name if manager else None

		pending = False
		if f["status"] != "Completed":
			if not cint(f["sessions_scheduled"]):
				# Awaiting scheduling — the master trainer's action.
				if scheduler:
					pending = True
			else:
				if f["is_manager"] and _has_unrecorded(f["name"], "manager_sessions"):
					pending = True
				if f["is_trainer"]:
					recorded = frappe.db.get_value(
						"Employee Feedback Trainer",
						{"parent": f["name"], "trainer": user},
						"recorded",
					)
					if not cint(recorded):
						pending = True
				if f["is_master"] and _has_unrecorded(f["name"], "master_sessions"):
					pending = True
		f["action_needed"] = pending

	return forms


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def _session_payload(r):
	return {
		"name": r.name,
		"meeting_datetime": r.meeting_datetime,
		"feedback": r.feedback,
		"recorded": cint(r.recorded),
		"recorded_by": r.recorded_by,
		"recorded_on": r.recorded_on,
	}


def _form_payload(form):
	user = frappe.session.user
	completed = form.status == "Completed"
	scheduled = cint(form.sessions_scheduled)
	my_row = next((r for r in form.trainer_feedback if r.trainer == user), None)

	return {
		"name": form.name,
		"status": form.status,
		"sessions_scheduled": scheduled,
		"master_trainer": form.master_trainer,
		"employee": form.employee,
		"employee_name": form.employee_name,
		"course": form.course,
		"course_title": form.course_title,
		"batch": form.batch,
		"completed_on": form.completed_on,
		"immediate_manager": form.immediate_manager,
		"immediate_manager_name": frappe.db.get_value("Employee", form.immediate_manager, "employee_name")
		if form.immediate_manager
		else None,
		"manager_sessions": [_session_payload(r) for r in form.manager_sessions],
		"master_sessions": [_session_payload(r) for r in form.master_sessions],
		"trainers": [
			{
				"name": r.name,
				"trainer": r.trainer,
				"trainer_name": r.trainer_name,
				"meeting_datetime": r.meeting_datetime,
				"feedback": r.feedback,
				"recorded": cint(r.recorded),
				"is_me": r.trainer == user,
			}
			for r in form.trainer_feedback
		],
		# Capability flags for the current user
		"can_schedule": can_schedule(user) and not scheduled and not completed,
		"can_reschedule": can_schedule(user) and scheduled and not completed,
		"can_edit_manager": can_edit_manager(form, user) and scheduled and not completed,
		"can_edit_trainer": bool(my_row) and scheduled and not completed,
		"my_trainer": my_row.trainer if my_row else None,
		"can_edit_master": can_act_master(form, user) and scheduled and not completed,
		"can_complete": can_act_master(form, user)
		and scheduled
		and not completed
		and ready_to_complete(form),
		"can_reopen": _is_admin(user) and completed,
		"is_readonly": completed,
	}


# ---------------------------------------------------------------------------
# Notifications (reuse the shared _notify helper: in-app Notification Log + email)
# ---------------------------------------------------------------------------


def _context(form):
	employee_name = form.employee_name or frappe.db.get_value(
		"Employee", form.employee, "employee_name"
	)
	course_title = form.course_title or frappe.db.get_value("LMS Course", form.course, "title")
	from_user = _employee_user(form.employee) or "Administrator"
	return employee_name, course_title, from_user


def _fan_out(recipients, from_user, subject, message, form_name):
	for recipient in {r for r in recipients if r}:
		_notify(recipient, from_user, subject, message, DOCTYPE, form_name)


def _form_trainers(form):
	"""All trainer Users on the form."""
	return [r.trainer for r in form.trainer_feedback if r.trainer]


def notify_form_created(form):
	employee_name, course_title, from_user = _context(form)
	manager_user = _manager_user(form)
	trainers = {r.trainer for r in form.trainer_feedback if r.trainer}
	masters = set(_get_master_trainers())

	if manager_user:
		_fan_out(
			[manager_user],
			from_user,
			_("Feedback due: {0} completed '{1}'").format(employee_name, course_title),
			_(
				"<strong>{0}</strong> has completed the course <strong>{1}</strong>. "
				"Please record your manager feedback on the employee feedback form."
			).format(employee_name, course_title),
			form.name,
		)

	_fan_out(
		trainers,
		from_user,
		_("Feedback requested: {0} completed '{1}'").format(employee_name, course_title),
		_(
			"You are a trainer for <strong>{0}</strong>, who has completed "
			"<strong>{1}</strong>. Please record your trainer feedback after the mock session."
		).format(employee_name, course_title),
		form.name,
	)

	_fan_out(
		masters - trainers - {manager_user},
		from_user,
		_("New feedback form: {0} completed '{1}'").format(employee_name, course_title),
		_(
			"A feedback form was created for <strong>{0}</strong> on completing "
			"<strong>{1}</strong>."
		).format(employee_name, course_title),
		form.name,
	)


def notify_manager_feedback(form):
	employee_name, course_title, from_user = _context(form)
	employee_user = _employee_user(form.employee)
	# Employee + all assigned trainers + master trainers (manager is the submitter).
	recipients = [employee_user, *_form_trainers(form), *_get_master_trainers()]
	_fan_out(
		recipients,
		from_user,
		_("Manager feedback recorded for '{0}'").format(course_title),
		_(
			"The immediate manager has recorded feedback for <strong>{0}</strong> "
			"on <strong>{1}</strong>."
		).format(employee_name, course_title),
		form.name,
	)


def notify_trainer_feedback(form, trainer):
	employee_name, course_title, from_user = _context(form)
	manager_user = _manager_user(form)
	employee_user = _employee_user(form.employee)
	# Employee + manager + master trainers + other assigned trainers (exclude the submitter).
	other_trainers = [t for t in _form_trainers(form) if t != trainer]
	recipients = [employee_user, manager_user, *_get_master_trainers(), *other_trainers]
	_fan_out(
		recipients,
		from_user,
		_("Trainer feedback recorded for '{0}'").format(course_title),
		_(
			"Trainer feedback was recorded for <strong>{0}</strong> on "
			"<strong>{1}</strong>."
		).format(employee_name, course_title),
		form.name,
	)


def notify_master_feedback(form):
	employee_name, course_title, from_user = _context(form)
	employee_user = _employee_user(form.employee)
	manager_user = _manager_user(form)
	# Employee + manager + all assigned trainers (master is the submitter).
	recipients = [employee_user, manager_user, *_form_trainers(form)]
	_fan_out(
		recipients,
		from_user,
		_("Master trainer feedback recorded for '{0}'").format(course_title),
		_(
			"The master trainer has recorded feedback for <strong>{0}</strong> "
			"on <strong>{1}</strong>."
		).format(employee_name, course_title),
		form.name,
	)


def notify_completed(form):
	employee_name, course_title, from_user = _context(form)
	employee_user = _employee_user(form.employee)
	manager_user = _manager_user(form)
	recipients = [
		employee_user,
		manager_user,
		*_get_master_trainers(),
		*get_users_with_role(HR_ROLE),
	]
	_fan_out(
		recipients,
		from_user,
		_("Feedback completed for {0} — '{1}'").format(employee_name, course_title),
		_(
			"The feedback form for <strong>{0}</strong> on <strong>{1}</strong> "
			"is now complete."
		).format(employee_name, course_title),
		form.name,
	)


def notify_trainer_added(form, trainer):
	"""A trainer was added to the assignment after the form already existed."""
	employee_name, course_title, from_user = _context(form)
	_fan_out(
		[trainer],
		from_user,
		_("You've been added as a trainer for {0}").format(employee_name),
		_(
			"You have been added as a trainer for <strong>{0}</strong> ({1}). The master "
			"trainer will schedule your feedback session."
		).format(employee_name, course_title),
		form.name,
	)


def _notify_roster_change(form):
	"""Nudge the master trainer / HR that the trainer roster changed and the sessions
	need (re)scheduling."""
	employee_name, course_title, from_user = _context(form)
	masters = [form.master_trainer] if form.master_trainer else _get_master_trainers()
	recipients = list(masters) + list(get_users_with_role(HR_ROLE))
	_fan_out(
		recipients,
		from_user,
		_("Trainer roster changed for {0}").format(employee_name),
		_(
			"The trainer roster for <strong>{0}</strong> ({1}) has changed. Please "
			"(re)schedule the feedback sessions."
		).format(employee_name, course_title),
		form.name,
	)


def notify_manager_assigned(form):
	"""A new immediate manager was assigned to an in-flight feedback form."""
	manager_user = _manager_user(form)
	if not manager_user:
		return
	employee_name, course_title, from_user = _context(form)
	times = [s.meeting_datetime for s in form.manager_sessions if s.meeting_datetime]
	when = (
		" " + _("Scheduled: {0}.").format(", ".join(format_datetime(t) for t in times))
		if times
		else ""
	)
	_fan_out(
		[manager_user],
		from_user,
		_("You are now the manager for {0}'s feedback").format(employee_name),
		_(
			"You are now the immediate manager for <strong>{0}</strong>'s feedback on "
			"<strong>{1}</strong>."
		).format(employee_name, course_title)
		+ when,
		form.name,
	)


# ---------------------------------------------------------------------------
# Permissions (wired in hooks.py)
# ---------------------------------------------------------------------------


def get_permission_query(user, doctype=None):
	"""Row-level scoping: a user sees a form if they are the employee, the immediate
	manager, or a trainer on it. Admins and master trainers (org-wide reviewers) see all."""
	if not user:
		user = frappe.session.user
	if _is_super(user):
		return None

	u = frappe.db.escape(user)
	return (
		"(`tabEmployee Feedback Form`.employee IN "
		f"(SELECT name FROM `tabEmployee` WHERE user_id = {u})"
		" OR `tabEmployee Feedback Form`.immediate_manager IN "
		f"(SELECT name FROM `tabEmployee` WHERE user_id = {u})"
		" OR `tabEmployee Feedback Form`.name IN "
		"(SELECT parent FROM `tabEmployee Feedback Trainer` "
		f"WHERE trainer = {u} AND parenttype = 'Employee Feedback Form'))"
	)


def has_permission(doc, ptype=None, user=None):
	if not user:
		user = frappe.session.user
	if _is_super(user):
		return True
	if _employee_user(doc.employee) == user:
		return True
	if doc.immediate_manager and _employee_user(doc.immediate_manager) == user:
		return True
	if any(r.trainer == user for r in (doc.get("trainer_feedback") or [])):
		return True
	return False
