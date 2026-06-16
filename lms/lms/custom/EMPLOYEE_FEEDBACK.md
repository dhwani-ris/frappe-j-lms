# Employee Feedback Module

End-to-end documentation for the **Employee Feedback Form** feature in the Jamboree
LMS (`lms` app, Frappe v16). A feedback form is auto-created when an employee
completes 100% of an **assigned** course; a Master Trainer schedules the review
meetings; the immediate manager, the assigned trainers and the master trainer each
record feedback; the master trainer marks it complete.

> Related: notification mechanics are summarised here and detailed in
> [`NOTIFICATIONS.md`](./NOTIFICATIONS.md).

---

## 1. At a glance

| | |
|---|---|
| **Parent DocType** | `Employee Feedback Form` (module **LMS**, not submittable, status-driven) |
| **Child tables** | `Employee Feedback Trainer` (one row per trainer) · `Employee Feedback Session` (manager & master sessions — **multiple per role**) |
| **Trigger** | `LMS Enrollment.progress >= 100` on an **assigned** course |
| **Reviewers** | Immediate manager (1..n sessions), assigned trainer(s), one master trainer (1..n sessions) |
| **UI** | frappe-ui portal (`/feedback`, `/feedback/:name`) + a small desk client script |
| **Lifecycle** | `Draft → Sessions Scheduled → Manager Feedback Added → Trainer Feedback Added → Completed` |

### Files

| Area | Path |
|---|---|
| Parent DocType | `lms/lms/doctype/employee_feedback_form/` (`.json`, `.py`, `.js`, `test_*.py`) |
| Trainer child | `lms/lms/doctype/employee_feedback_trainer/` (`.json`, `.py`) |
| Session child (manager/master) | `lms/lms/doctype/employee_feedback_session/` (`.json`, `.py`) |
| Backend logic / API | `lms/lms/custom/employee_feedback.py` |
| Data migration | `lms/patches/v2_0/migrate_feedback_to_sessions.py` (in `patches.txt`, post-model-sync) |
| Scheduling notification | `lms/lms/custom/notifications.py` (`notify_feedback_scheduled`) |
| Hooks (events + perms) | `lms/hooks.py` |
| Role permissions | `lms/lms/custom/jamboree_setup.py` |
| User-info flag | `lms/lms/api.py` (`get_user_info` → `has_employee_feedback`) |
| Portal pages | `frontend/src/pages/EmployeeFeedbackForm.vue`, `EmployeeFeedback.vue` |
| Portal components | `frontend/src/components/FeedbackBlock.vue`, `EmployeeFeedbackList.vue` |
| Routes | `frontend/src/router.js` (`/feedback`, `/feedback/:name`) |
| Left-menu item | `frontend/src/utils/index.js` (Management → Employee Feedback) |

---

## 2. Why it diverges from the original BRD

The BRD (`lms/New Brd/employee_feedback_implementation (2).html`) assumed generic
Frappe-desk patterns; the implementation reconciles them with how Jamboree actually
works. Confirmed decisions:

| BRD assumption | Reality / decision |
|---|---|
| Master trainer is an Employee field, auto-fetched | Master trainers are **org-wide** (role profile `Jamboree Master Trainer`); the form's `master_trainer` is **self-assigned by whoever schedules**. |
| Trainers added manually | Trainers are **pre-filled** from the assignment micro-batch's `Course Instructor` rows. |
| Desk Workflow + Workspace/sidebar | **frappe-ui portal**; status is controller-driven, no desk Workflow. |
| One form per learner who hits 100% | **Assigned employees only** (must have a micro-batch + active Employee); one per `employee + course`. |
| Each reviewer sets their own meeting time | The **Master Trainer schedules all meeting times** up front; reviewers only write feedback. |

---

## 3. Data model

### Parent — `Employee Feedback Form`

**Employee Information**

| Field | Type | Notes |
|---|---|---|
| `employee` | Link → Employee | Mandatory, read-only. `ignore_user_permissions`. Set by the auto-creation hook. |
| `employee_name` | Data | `fetch_from: employee.employee_name`, read-only |
| `course` | Link → LMS Course | Mandatory, read-only |
| `course_title` | Data | `fetch_from: course.title`, read-only |
| `batch` | Link → LMS Batch | The assignment micro-batch (source of trainer rows), read-only |
| `completed_on` | Date | When progress hit 100%, read-only |
| `immediate_manager` | Link → Employee | `fetch_from: employee.reports_to`, read-only. `ignore_user_permissions`. |
| `status` | Select | `Draft / Sessions Scheduled / Manager Feedback Added / Trainer Feedback Added / Completed`. Controller-driven, read-only, in list view. |
| `sessions_scheduled` | Check | Set when the MT confirms the schedule. Gates feedback + locks times. Read-only. |

**Manager Feedback** — `manager_sessions` (Table → `Employee Feedback Session`). **Zero or
more** sessions, all belonging to the single immediate manager. (Empty when the employee
has no manager.)

**Trainer Feedback** — `trainer_feedback` (Table → `Employee Feedback Trainer`), one row
per assigned trainer.

**Master Trainer Feedback**

| Field | Type | Notes |
|---|---|---|
| `master_trainer` | Link → User | The MT who scheduled (self-assigned). `ignore_user_permissions`. Only this user / admin records master feedback + completes. |
| `master_sessions` | Table → `Employee Feedback Session` | **One or more** master sessions, all belonging to the assigned master trainer. |

### Child — `Employee Feedback Trainer` (`istable`)

| Field | Type | Notes |
|---|---|---|
| `trainer` | Link → **User** | The instructor (Users, not necessarily Employees). Mandatory, in list view. |
| `trainer_name` | Data | `fetch_from: trainer.full_name`, read-only |
| `meeting_datetime` | Datetime | **Set by the MT when scheduling**; the trainer cannot edit it |
| `feedback` | Text Editor | Written by that trainer |
| `recorded` | Check | Set when time + feedback present, read-only |

### Child — `Employee Feedback Session` (`istable`)

Used for **both** `manager_sessions` and `master_sessions` — one row = one meeting + its
own feedback. The "who" is implied by which table the row sits in (manager = the immediate
manager, master = the assigned `master_trainer`).

| Field | Type | Notes |
|---|---|---|
| `meeting_datetime` | Datetime | **Set by the MT when scheduling** |
| `feedback` | Text Editor | Written by the manager / master trainer for that session |
| `recorded` | Check | Set when time + feedback present, read-only |
| `recorded_by` / `recorded_on` | Link → User / Datetime | Stamped on the 0→1 edge (audit) |

---

## 4. Lifecycle

```
                 (LMS Enrollment.progress = 100, assigned course)
                                   │  auto-create
                                   ▼
                                Draft ───────────────────────────┐
        schedule_sessions (Master Trainer / admin)               │ reopen_feedback (HR/admin)
        ├─ validate order / gap / future / conflicts             │
        └─ self-assign master_trainer, notify everyone           │
                                   ▼                              │
                          Sessions Scheduled                     │
        save_manager_feedback / save_trainer_feedback /          │
        save_master_feedback  (feedback text only; any order)    │
                                   ▼                              │
        Manager Feedback Added → Trainer Feedback Added           │
        complete_feedback (assigned master_trainer / admin)      │
                                   ▼                              │
                              Completed ───────────────────────────┘
        reschedule_sessions (MT/admin, any non-Completed) → back to Draft (feedback kept)
```

- **Status** is recomputed in `EmployeeFeedbackForm.compute_status()`:
  `Draft` when not scheduled; once scheduled → `Sessions Scheduled`, then
  `Manager Feedback Added` (manager done), then `Trainer Feedback Added` (manager
  done **and** every trainer row recorded). `Completed` is set **only** by the
  explicit complete action. When the employee has **no manager**, the manager step
  is skipped.
- **Feedback recording is unordered** — manager / trainers / master may record in any
  sequence after scheduling. The only enforced ordering is on the **meeting times**.
- A **Completed** form is **locked** (any edit throws) until an admin reopens it.

---

## 5. Auto-creation

`create_feedback_form_on_completion(doc, method)` — wired on `LMS Enrollment.on_update`
in `hooks.py` (alongside the existing completion notifier):

1. Skip unless `cint(doc.progress) >= 100`.
2. Resolve the active `Employee` for `doc.member` (the learner's User). No Employee → skip.
3. Resolve the **assignment micro-batch**: a batch the member is enrolled in
   (`LMS Batch Enrollment`) that carries the course (`Batch Course`). None → skip
   (self-enrolled / non-assigned courses get no form).
4. Skip if a form already exists for `employee + course` (uniqueness).
5. Create the form (`employee`, `course`, `batch`, `completed_on`, `status="Draft"`)
   and **pre-fill** one trainer row per `Course Instructor` on the batch.
6. Fire the **form-created** notification.

> The assignment itself is created by `course_assignment.py::assign_course_to_student()`,
> which builds the one-student micro-batch and stores the chosen trainers as
> `Course Instructor` rows on the `LMS Batch`.

---

## 6. Scheduling (Master Trainer)

`schedule_sessions(name, manager_times, master_times, trainer_times)`

- **Who:** any Master Trainer (`LMS Master Trainer`) or admin (`System Manager` / `LMS HR` / Administrator).
- `manager_times` / `master_times` are lists of `{"row": <existing session row, optional>, "meeting_datetime": ...}` — **the MT decides how many** manager and master sessions to add/remove. `trainer_times` is a list of `{"row": <trainer row>, "meeting_datetime": ...}` (or `{"trainer": <user>, ...}`); trainer rows are fixed (one per instructor).
- The manager/master tables are **reconciled** against the payload (`_reconcile_sessions`) — rows kept by name retain their feedback, new rows are created, omitted rows dropped.
- Sets all meeting times, **self-assigns** the caller as `master_trainer`, runs the
  conflict check, then saves with `flags.scheduling` → `validate_schedule()` enforces:
  - **At least one** manager session (when the employee has a manager) and **one** master session.
  - **All present** — every session must have a time.
  - **Future only** — every time must be after "now".
  - **Strict group order** — all manager sessions (in row order) < all trainer sessions (in row order) < all master sessions (in row order).
  - **≥15-min gap** — each consecutive pair at least 15 minutes apart.
- On success → `sessions_scheduled = 1`, status `Sessions Scheduled`, and the
  **sessions-scheduled** notification fans out.

### Conflict check (overlapping 15-minute blocks)

Each meeting is a 15-minute block `[T, T+15min)`. For each participant (manager,
every trainer, the master = scheduler), the candidate time is rejected if it
**overlaps** (`abs(other − candidate) < 15 min`) any meeting that participant already
has on **another, not-Completed** form — resolved by `_busy_blocks(user, exclude_form)`
across:

- the **manager slot** of forms they manage (`immediate_manager.user_id == user`),
- their **trainer-row** slots (`Employee Feedback Trainer.trainer == user`),
- the **master slot** of forms where they are `master_trainer`.

Error: `"<participant> already has a feedback session scheduled around <time>."`

### Lock & reschedule

- Times are **locked** after confirm: a guard in `validate()` throws if any meeting
  datetime changes on a scheduled form outside a (re)schedule.
- `reschedule_sessions(name)` (MT/admin, any non-Completed form) sets
  `flags.rescheduling` → back to `Draft` with times editable; **feedback already
  entered is preserved**; whoever re-confirms becomes the new `master_trainer`; the
  schedule notification is re-sent.

---

## 7. Recording feedback & completion

All require `sessions_scheduled` (else `"Feedback can be recorded only after the
sessions are scheduled."`). Feedback methods take **only** the feedback text — the
meeting time is owned by the MT.

| Method | Who | Effect |
|---|---|---|
| `save_manager_feedback(name, feedback, row)` | the immediate manager / admin | records that **manager session** (`row`); notifies employee + master trainers |
| `save_trainer_feedback(name, feedback, trainer=None)` | the trainer on that row / admin | records that trainer row; notifies trainer + manager + master trainers |
| `save_master_feedback(name, feedback, row)` | the form's `master_trainer` / admin | records that **master session** (`row`), stamps `recorded_by` |
| `complete_feedback(name)` | the form's `master_trainer` / admin | gate then status `Completed` |
| `reopen_feedback(name)` | `LMS HR` / `System Manager` / Administrator | `Completed → Draft` (unscheduled) |

**Completion gate** (`validate_completion`): **every** manager session (when the employee
has a manager), **every** trainer row, and **every** master session recorded — else
`"Manager, all trainer, and master trainer feedback must be completed before submitting."`
Status reaches `Manager Feedback Added` only once **all** manager sessions are recorded;
`Trainer Feedback Added` once manager + **all** trainers are done.

---

## 8. Permissions & visibility

Wired in `hooks.py`:

```python
permission_query_conditions["Employee Feedback Form"] = "lms.lms.custom.employee_feedback.get_permission_query"
has_permission["Employee Feedback Form"]              = "lms.lms.custom.employee_feedback.has_permission"
```

- **Row scoping** (`get_permission_query`): a user sees a form if they are the
  **employee**, the **immediate manager**, or a **trainer on it** (sub-query on
  `Employee Feedback Trainer.trainer`). **Admins and master trainers see all.**
  `has_permission` mirrors this for single-doc access.
- **Role perms** (DocType JSON, mirrored as Custom DocPerm in `jamboree_setup.py`):

  | Role | Read | Write | Create | Notes |
  |---|---|---|---|---|
  | System Manager / LMS HR | ✓ | ✓ | ✓ | full; can reopen |
  | LMS Master Trainer | ✓ | ✓ | — | sees all; only the assigned one acts as master |
  | LMS Manager | ✓ | ✓ | — | scoped to forms they manage |
  | LMS Trainer | ✓ | ✓ | — | scoped to forms they appear on |
  | LMS Student | ✓ | — | — | scoped by the query to **their own** form only (the evaluatee) |

- **`ignore_user_permissions: 1`** on `employee`, `immediate_manager`, `master_trainer`:
  Jamboree sets a per-employee `User Permission` (Employee = self) on each user;
  without this flag Frappe would AND that restriction onto these Employee/User links
  and hide a form from its own trainers / manager / evaluatee. Visibility is governed
  **solely** by the permission query.
- **Per-action checks** in the whitelisted methods are the real enforcement (e.g. only
  the assigned `master_trainer`/admin can record master feedback or complete);
  the role-level `write` is intentionally broad and narrowed by these checks.

> **Custom DocPerm note:** because Jamboree uses Custom DocPerm for LMS doctypes,
> those override the DocType-JSON perms. After deploying, run
> `lms.lms.custom.jamboree_setup.create_jamboree_custom_docperms()` (or
> `setup_jamboree_roles()`) so the role rows — including `LMS Student` read — are
> present.

---

## 9. Notifications

All use the shared `_notify(recipient, from_user, subject, message, ref_doctype,
ref_name)` helper → an in-app **Notification Log** entry **and** an email. The
scheduling notification lives in `notifications.py`; the lifecycle ones in
`employee_feedback.py`. See [`NOTIFICATIONS.md`](./NOTIFICATIONS.md) for the canonical
table.

| Event | Function | Recipients |
|---|---|---|
| Form created | `employee_feedback.notify_form_created` | manager + every pre-filled trainer + all master trainers |
| **Sessions scheduled** | `notifications.notify_feedback_scheduled` | each participant gets **their slot**; the **employee** gets the **full schedule** |
| Manager feedback recorded | `employee_feedback.notify_manager_feedback` | employee + all master trainers |
| Trainer feedback recorded | `employee_feedback.notify_trainer_feedback` | that trainer + manager + all master trainers |
| Completed | `employee_feedback.notify_completed` | employee + manager + all master trainers + HR |

- Master trainers for the **org-wide** events resolve via `_get_master_trainers()`
  (role profile `Jamboree Master Trainer`); the **scheduled** message targets the
  **assigned** `master_trainer` for the master slot.
- Recipients are de-duplicated and `None`/disabled users skipped. Email failures are
  caught and logged — they never abort a save.

---

## 10. Portal UI (frappe-ui)

- **Routes** (`router.js`): `/feedback` → `EmployeeFeedback.vue` (list of all forms the
  user can act on/view); `/feedback/:name` → `EmployeeFeedbackForm.vue`.
- **`EmployeeFeedbackForm.vue`** loads `get_feedback_form(name)` and renders by
  capability flags:
  - **Schedule panel** (when `can_schedule`): an **add/remove list** of datetime
    pickers for manager sessions, a picker per trainer, and an add/remove list for
    master sessions + **Confirm Schedule**; once scheduled a **Reschedule** button appears.
  - Feedback sections are **locked until `sessions_scheduled`**; each manager and master
    **session** renders its own block (read-only scheduled time + feedback); each reviewer
    edits only their own sessions/row; the assigned master trainer gets **Complete &
    Submit**; HR/admin gets **Reopen**.
- **`FeedbackBlock.vue`** — one manager/master **session** (read-only scheduled time +
  feedback textarea), rendered once per session row. **`EmployeeFeedbackList.vue`** — the "pending feedback" card,
  embedded in Trainer Dashboard, Manager Dashboard and Employee Detail.
- **Left menu**: a **Management → Employee Feedback** item (`utils/index.js`,
  `canSeeEmployeeFeedback()`) shown to System Manager / reviewers, and to an
  **evaluatee only when they have a form** — gated by the `has_employee_feedback`
  flag added to `get_user_info` (`lms/lms/api.py`).
- A small desk client script (`employee_feedback_form.js`) exposes Complete / Reopen
  for admins working in the desk.

### Capability flags returned by `get_feedback_form` / `list_my_feedback_forms`

`can_schedule`, `can_reschedule`, `can_edit_manager`, `can_edit_trainer`,
`can_edit_master`, `can_complete`, `can_reopen`, `is_readonly`, plus
`sessions_scheduled`, `master_trainer`, and per-form role context (`is_manager`,
`is_trainer`, `is_master`, `action_needed`). The frontend renders strictly from these.

---

## 11. Tests

`lms/lms/doctype/employee_feedback_form/test_employee_feedback_form.py` (FrappeTestCase):

- auto-creation (trainers pre-filled, manager set), idempotency, self-enrolled skip;
- scheduling: MT-only, sets state + `master_trainer`; rejections for bad order,
  <15-min gap, past time, missing slot; cross-form trainer conflict;
- feedback blocked before scheduling; full record → completion gate → lock → reopen;
- master feedback/complete restricted to the assigned `master_trainer`;
- reschedule returns to Draft and preserves feedback;
- no-manager form schedules without a manager slot and completes without manager feedback;
- permission scoping (trainer sees own, unrelated student does not);
- creation and scheduled notifications.

Cleanup is **scoped to the suite's test learners** so real data on the shared site is
never touched (some hooks commit mid-test, so rollback alone can't isolate).

```bash
bench --site <site> run-tests --module lms.lms.doctype.employee_feedback_form.test_employee_feedback_form
```

---

## 12. Deploy checklist

1. `bench --site <site> migrate` — installs/updates the DocTypes.
2. `bench --site <site> execute lms.lms.custom.jamboree_setup.create_jamboree_custom_docperms`
   (or `…setup_jamboree_roles`) — ensures the role permissions (incl. `LMS Student` read).
3. `bench --site <site> clear-cache`.
4. `cd apps/lms/frontend && yarn build` — builds the portal pages/components.
5. Confirm the `LMS Enrollment` `on_update` hook list and the `Employee Feedback Form`
   permission hooks are active (a cache clear / migrate picks them up).

---

## 13. Edge cases & guarantees

- **Multiple manager/master sessions** → the MT adds as many manager and master sessions
  as needed at scheduling; the group order + ≥15-min gap apply across all of them, and a
  role is "done" only when **all** its sessions are recorded.
- **Migration** → existing forms (pre-sessions schema) are converted by
  `patches/v2_0/migrate_feedback_to_sessions.py`: the old single manager/master feedback
  becomes one session row each. Frappe leaves the old columns in place (orphan), so the
  patch reads them post-sync; it is idempotent.
- **No immediate manager** → manager sessions are empty; manager step skipped in
  scheduling and not required for completion.
- **Reschedule** reassigns `master_trainer` to whoever re-confirms; feedback preserved.
- **Conflict check** ignores `Completed` forms (their sessions are done).
- **Within-form overlaps** are impossible (strict order + ≥15-min gap).
- **Future-only** is enforced at confirm; **times lock** after confirm (tamper guard).
- A non-owner master trainer can **view** any form but cannot record master feedback or
  complete — only the assigned `master_trainer` (or an admin) can.
- **One form per `employee + course`**; repeat course assignments would need an
  attempt/cycle field (not in scope).
