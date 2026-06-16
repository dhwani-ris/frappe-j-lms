"""Migrate the single manager/master feedback (pre-sessions schema) into the new
``manager_sessions`` / ``master_sessions`` child tables.

The Employee Feedback Form used to hold one manager meeting + feedback and one master
meeting + feedback directly on the parent. Those became multi-row session tables
(`Employee Feedback Session`). Frappe does not drop removed columns on migrate, so the
old values still live as orphan columns on `tabEmployee Feedback Form` and we copy each
into a single session row. Runs once (idempotent).
"""

import frappe

DOCTYPE = "Employee Feedback Form"


def execute():
	if not frappe.db.table_exists(DOCTYPE):
		return

	columns = set(frappe.db.get_table_columns(DOCTYPE))
	if "manager_meeting_datetime" not in columns and "master_meeting_datetime" not in columns:
		return  # fresh install / already migrated — no orphan columns to read

	rows = frappe.db.sql(
		"""
		SELECT name,
			manager_meeting_datetime, manager_feedback, manager_feedback_done,
			manager_feedback_by, manager_feedback_on,
			master_meeting_datetime, master_feedback, master_feedback_done,
			master_feedback_by, master_feedback_on
		FROM `tabEmployee Feedback Form`
		""",
		as_dict=True,
	)

	migrated = 0
	for r in rows:
		migrated += _migrate_block(r, "manager_sessions", "manager_")
		migrated += _migrate_block(r, "master_sessions", "master_")

	if migrated:
		frappe.db.commit()
		print(f"Employee Feedback: migrated {migrated} feedback block(s) into session rows")


def _migrate_block(row, parentfield, prefix):
	dt = row.get(prefix + "meeting_datetime")
	feedback = row.get(prefix + "feedback")
	if not (dt or feedback):
		return 0

	# Don't double-create if a session already exists for this form + table.
	if frappe.db.exists(
		"Employee Feedback Session", {"parent": row["name"], "parentfield": parentfield}
	):
		return 0

	frappe.get_doc(
		{
			"doctype": "Employee Feedback Session",
			"parenttype": DOCTYPE,
			"parentfield": parentfield,
			"parent": row["name"],
			"meeting_datetime": dt,
			"feedback": feedback,
			"recorded": row.get(prefix + "feedback_done") or 0,
			"recorded_by": row.get(prefix + "feedback_by"),
			"recorded_on": row.get(prefix + "feedback_on"),
		}
	).insert(ignore_permissions=True)
	return 1
