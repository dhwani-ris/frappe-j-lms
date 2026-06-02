# Jamboree LMS — Custom Notifications

All custom notification logic lives in [`notifications.py`](./notifications.py) and is
wired up in `lms/hooks.py` (`doc_events` + `scheduler_events`). Each notification
creates an in-app **Notification Log** entry; the deadline reminder additionally
sends an **email**.

| Notification | Trigger | Recipients |
|---|---|---|
| Quiz submitted | `LMS Quiz Submission` `after_insert` | Course instructors (batch trainers) |
| Course completed | `LMS Enrollment` `on_update` (progress = 100) | Instructors + manager |
| Student behind | Daily — `check_student_progress_alerts` | Manager (`reports_to`) |
| **Course deadline approaching** | Daily — `check_course_deadline_reminders` | **Student + trainers + master trainers + manager** |

---

## Course deadline approaching reminder

**Function:** `check_course_deadline_reminders()` · **Schedule:** daily.

### What it does

For every **batch** whose `end_date` is **0, 1 or 2 days away**, and for every
`(enrolled employee, course)` pair in that batch where the course is **not yet
completed** (`LMS Enrollment.progress < 100`), it sends an **in-app notification
and an email** to four parties:

| Recipient | How it is resolved |
|---|---|
| **Employee (student)** | The batch-enrolled member. Gets a first-person message. |
| **Trainer(s)** | The `Course Instructor` rows on the batch (`instructors`). |
| **Master trainer(s)** | All enabled users whose **role profile** is `Jamboree Master Trainer` (set on the User while creating an employee at `/lms/employees`). Org-wide, not per-employee. |
| **Manager** | `Employee.reports_to` of the employee → that manager's `user_id`. |

Recipients are de-duplicated; the student is always messaged separately (first
person), everyone else gets the third-person version.

### When it fires

The job runs **once a day**. Because the window is inclusive (`0..2` days), an
incomplete assignment is reminded on **each of the final three days** before the
deadline, with escalating wording:

- 2 days out → *"… is due in 2 days (2 days remaining)"*
- 1 day out → *"… is due tomorrow (1 day remaining)"*
- due today → *"… is due today (the deadline is today)"*

Completed courses (`progress >= 100`) and batches outside the window are skipped.
Overdue batches (`end_date` in the past) are **not** reminded — only the run-up to
the deadline.

### Configuration knobs

Both live at the top of `notifications.py`:

- `MASTER_TRAINER_ROLE_PROFILE = "Jamboree Master Trainer"` — the role profile that
  identifies master trainers.
- `DEADLINE_REMINDER_WINDOW_DAYS = 2` — how many days before the deadline to start
  reminding.

### Operational notes

- **Email delivery depends on a working outbound email account.** If the site has no
  valid Email Account / SMTP, the in-app notifications still appear but emails land in
  the Email Queue as *"Failed to send email"*. Email failures are caught and logged;
  they never abort the daily run.
- Activating a newly added scheduler entry requires syncing the job list (run
  `bench --site <site> migrate`, or
  `bench --site <site> execute frappe.core.doctype.scheduled_job_type.scheduled_job_type.sync_jobs`).
  Confirm with the `Scheduled Job Type` list — the entry
  `notifications.check_course_deadline_reminders` should be **Daily** and not stopped.

### Tests

`test_course_deadline_reminders.py` covers:

1. all four recipients receive both an in-app notification and an email;
2. a completed course produces nothing;
3. a batch outside the 2-day window produces nothing.

Run them with:

```bash
bench --site <site> run-tests --module lms.lms.custom.test_course_deadline_reminders
```
