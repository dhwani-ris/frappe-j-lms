import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist()
def get_direct_reports(manager_employee_id=None):
    """Get direct reports for a manager using Employee.reports_to."""
    if not manager_employee_id:
        manager_employee_id = frappe.db.get_value(
            "Employee",
            {"user_id": frappe.session.user, "status": "Active"},
            "name",
        )
    if not manager_employee_id:
        return []

    reports = frappe.get_all(
        "Employee",
        filters={"reports_to": manager_employee_id, "status": "Active"},
        fields=[
            "name",
            "employee_name",
            "user_id",
            "department",
            "designation",
            "image",
        ],
    )
    return reports


@frappe.whitelist()
def get_manager_dashboard():
    """Manager dashboard: direct reports' learning progress (read-only)."""
    frappe.only_for(
        ["LMS Manager", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"]
    )

    user_roles = frappe.get_roles(frappe.session.user)
    is_super = "System Manager" in user_roles or "LMS HR" in user_roles

    if is_super:
        # System Manager / HR: show ALL active employees
        reports = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=[
                "name",
                "employee_name",
                "user_id",
                "department",
                "designation",
                "image",
            ],
        )
    else:
        reports = get_direct_reports()

    for report in reports:
        if not report.user_id:
            report.enrollments = []
            report.total_courses = 0
            report.completed = 0
            report.avg_progress = 0
            report.quiz_scores = []
            report.avg_quiz_score = 0
            report.assignment_scores = []
            report.avg_assignment_score = 0
            continue

        enrollments = frappe.get_all(
            "LMS Enrollment",
            {"member": report.user_id},
            ["course", "progress", "modified"],
        )
        for enrollment in enrollments:
            enrollment.course_title = frappe.db.get_value(
                "LMS Course", enrollment.course, "title"
            )

        # Get quiz scores
        quiz_submissions = frappe.get_all(
            "LMS Quiz Submission",
            {"member": report.user_id},
            ["quiz", "score", "percentage", "creation"],
            order_by="creation desc",
        )
        for quiz_sub in quiz_submissions:
            quiz_title = frappe.db.get_value("LMS Quiz", quiz_sub.quiz, "title")
            quiz_sub.quiz_title = quiz_title

        # Get assignment scores
        assignment_submissions = frappe.get_all(
            "LMS Assignment Submission",
            {"member": report.user_id},
            ["assignment", "status", "assignment_title", "modified"],
            order_by="modified desc",
        )

        report.enrollments = enrollments
        report.total_courses = len(enrollments)
        report.completed = len([e for e in enrollments if cint(e.progress) >= 100])
        report.avg_progress = (
            round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
            if enrollments
            else 0
        )
        report.quiz_scores = quiz_submissions
        report.avg_quiz_score = (
            round(
                sum(float(q.get("percentage", 0) or 0) for q in quiz_submissions)
                / len(quiz_submissions),
                1,
            )
            if quiz_submissions
            else 0
        )
        report.assignment_scores = assignment_submissions
        passed_assignments = len(
            [a for a in assignment_submissions if a.status == "Pass"]
        )
        report.avg_assignment_score = (
            round((passed_assignments / len(assignment_submissions)) * 100, 1)
            if assignment_submissions
            else 0
        )

    return {
        "reports": reports,
        "summary": {
            "team_size": len(reports),
            "avg_progress": (
                round(sum(r.avg_progress for r in reports) / len(reports), 1)
                if reports
                else 0
            ),
            "total_completed": sum(r.completed for r in reports),
        },
    }


def _get_course_chapter_structure(course, _cache):
    """Return ordered chapters for a course.

    Shape: [{name, title, idx, is_scorm, lessons: [lesson_name, ...]}], ordered by idx.
    Cached in the dict ``_cache`` so each course's structure is built only once per request.
    """
    if course in _cache:
        return _cache[course]

    chapter_refs = frappe.get_all(
        "Chapter Reference", {"parent": course}, ["chapter", "idx"], order_by="idx"
    )
    chapters = []
    for ref in chapter_refs:
        cd = frappe.db.get_value(
            "Course Chapter",
            ref.chapter,
            ["name", "title", "is_scorm_package"],
            as_dict=True,
        )
        if not cd:
            continue
        lessons = frappe.get_all(
            "Lesson Reference", {"parent": ref.chapter}, pluck="lesson"
        )
        chapters.append(
            {
                "name": cd.name,
                "title": cd.title,
                "idx": ref.idx,
                "is_scorm": cint(cd.is_scorm_package),
                "lessons": lessons,
            }
        )

    _cache[course] = chapters
    return chapters


def _get_unlockable_chapters(course, member, chapters, course_title, sequential_cache):
    """Return the chapters the member can be *offered to unlock* in a course.

    These are exactly the entries that surface in the trainer dashboard's "Unlock Chapter"
    action button. A course only contributes entries when sequential learning is enabled and
    the member has a first-incomplete chapter that is not the last chapter. Following the
    established convention of ``get_locked_chapters_for_employee``, each entry's *identity*
    (``chapter``/``name``) is that first-incomplete chapter (the actual unlock target) while
    the *display* fields point at the NEXT chapter — the one the member visibly gains access
    to. ``display_chapter`` is that next chapter's name, used for filtering.

    This helper is the single source of truth shared by both the dashboard's Course/Chapter
    filters and ``get_locked_chapters_for_employee``, so the filters always match the button.
    It is member-aware and bulk-fetches progress in one query (no per-lesson lookups).
    """
    if course not in sequential_cache:
        sequential_cache[course] = cint(
            frappe.db.get_value("LMS Course", course, "enable_sequential_learning")
        )

    if not sequential_cache[course]:
        return []  # Non-sequential courses never lock anything, so nothing to unlock.

    rows = frappe.get_all(
        "LMS Course Progress",
        {"member": member, "course": course},
        ["lesson", "chapter", "status", "manually_unlocked"],
    )
    complete_lessons = {r.lesson for r in rows if r.lesson and r.status == "Complete"}
    complete_chapters = {r.chapter for r in rows if r.chapter and r.status == "Complete"}
    unlocked = {r.chapter for r in rows if r.chapter and r.manually_unlocked}

    entries = []
    all_prev_complete = True
    for idx, ch in enumerate(chapters):
        # Already manually unlocked: skip without affecting the gate (matches existing logic).
        if ch["name"] in unlocked:
            continue

        if ch["lessons"]:
            ch_complete = all(lesson in complete_lessons for lesson in ch["lessons"])
        else:
            # SCORM / lessonless chapter: completion is tracked at the chapter level.
            ch_complete = ch["name"] in complete_chapters

        # The first incomplete chapter whose predecessors are all complete is the unlock
        # target — but only when there is a following chapter for the member to gain access
        # to (unlocking the last chapter is pointless, so it is not offered).
        if not ch_complete and all_prev_complete and idx + 1 < len(chapters):
            nxt = chapters[idx + 1]
            entries.append(
                {
                    # Identity = first incomplete chapter (the actual unlock target).
                    "chapter": ch["name"],
                    "name": ch["name"],
                    "course": course,
                    "course_title": course_title,
                    # Display = the NEXT chapter the member gains access to.
                    "chapter_title": nxt["title"],
                    "title": nxt["title"],
                    "idx": nxt["idx"],
                    "display_chapter": nxt["name"],
                    "display": f"{course_title} - {nxt['title']}",
                }
            )

        if not ch_complete:
            all_prev_complete = False

    return entries


@frappe.whitelist()
def get_trainer_dashboard():
    """Trainer dashboard: batches where user is instructor + student progress."""
    frappe.only_for(
        ["LMS Trainer", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"]
    )

    user_roles = frappe.get_roles(frappe.session.user)
    is_super = (
        "System Manager" in user_roles
        or "LMS HR" in user_roles
        or "LMS Master Trainer" in user_roles
    )

    if is_super:
        # System Manager / HR / Master Trainer: show ALL batches
        batch_names = frappe.get_all("LMS Batch", pluck="name")
        instructor_courses = frappe.get_all("LMS Course", pluck="name")
    else:
        # Get batches and courses where current user is an instructor
        instructor_records = frappe.get_all(
            "Course Instructor",
            {"instructor": frappe.session.user},
            ["parent", "parenttype"],
        )
        batch_names = list(
            set([r.parent for r in instructor_records if r.parenttype == "LMS Batch"])
        )
        instructor_courses = list(
            set([r.parent for r in instructor_records if r.parenttype == "LMS Course"])
        )

    batches_data = []
    total_students = 0
    total_progress = 0
    student_count_for_avg = 0
    pending_evaluations = 0
    seen_students = set()  # Track unique students for stats only

    # Request-scoped caches + course list for the Course/Chapter filters.
    chapter_cache = {}  # course -> ordered chapter structure (built once per course)
    sequential_cache = {}  # course -> enable_sequential_learning (0/1)
    courses_seen = {}  # course -> {name, title, chapters: [{name, title, idx}]}

    # Process batches
    for batch_name in batch_names:
        # Check if this is actually an LMS Batch
        if not frappe.db.exists("LMS Batch", batch_name):
            continue

        batch = frappe.db.get_value(
            "LMS Batch",
            batch_name,
            ["name", "title", "start_date", "end_date"],
            as_dict=True,
        )

        # Get courses assigned to this batch
        batch_courses = frappe.get_all(
            "Batch Course", {"parent": batch_name}, ["course"], pluck="course"
        )

        students = frappe.get_all(
            "LMS Batch Enrollment",
            {"batch": batch_name},
            ["member", "member_name"],
        )

        for student in students:
            # Get only enrollments for courses in this batch
            if batch_courses:
                enrollments = frappe.get_all(
                    "LMS Enrollment",
                    {"member": student.member, "course": ["in", batch_courses]},
                    ["course", "progress"],
                )
            else:
                # If no specific courses, show all enrollments
                enrollments = frappe.get_all(
                    "LMS Enrollment",
                    {"member": student.member},
                    ["course", "progress"],
                )

            for e in enrollments:
                e.course_title = frappe.db.get_value("LMS Course", e.course, "title")
                e.status = calculate_status(cint(e.progress))

                # Enrich with the chapters this employee can be offered to unlock — the same
                # data that drives their "Unlock Chapter" action button. The Course/Chapter
                # filters are built from these, so a course/chapter only appears (and an
                # employee only matches) when it is actionable for that employee.
                course_chapters = _get_course_chapter_structure(e.course, chapter_cache)
                unlockable = _get_unlockable_chapters(
                    e.course,
                    student.member,
                    course_chapters,
                    e.course_title,
                    sequential_cache,
                )
                # The display-chapter names the chapter filter matches against.
                e.actionable_chapters = [u["display_chapter"] for u in unlockable]

                if unlockable:
                    course_entry = courses_seen.setdefault(
                        e.course,
                        {"name": e.course, "title": e.course_title, "chapters": {}},
                    )
                    for u in unlockable:
                        # Dedup by display-chapter; only chapters seen in some button appear.
                        course_entry["chapters"][u["display_chapter"]] = {
                            "name": u["display_chapter"],
                            "title": u["chapter_title"],
                            "idx": u["idx"],
                        }

            # Get quiz submissions only for courses in this batch
            if batch_courses:
                # Get all quizzes for courses in this batch
                batch_course_quizzes = frappe.get_all(
                    "LMS Quiz", {"course": ["in", batch_courses]}, pluck="name"
                )

                # Get quiz scores - only for quizzes in this batch's courses
                if batch_course_quizzes:
                    quiz_submissions = frappe.get_all(
                        "LMS Quiz Submission",
                        {
                            "member": student.member,
                            "quiz": ["in", batch_course_quizzes],
                        },
                        ["quiz", "score", "percentage", "creation"],
                        order_by="creation desc",
                    )
                else:
                    quiz_submissions = []
            else:
                # No specific courses in batch - show all quiz submissions
                quiz_submissions = frappe.get_all(
                    "LMS Quiz Submission",
                    {"member": student.member},
                    ["quiz", "score", "percentage", "creation"],
                    order_by="creation desc",
                )

            for quiz_sub in quiz_submissions:
                quiz_title = frappe.db.get_value("LMS Quiz", quiz_sub.quiz, "title")
                quiz_sub.quiz_title = quiz_title

            # Get assignment submissions only for courses in this batch
            if batch_courses:
                assignment_submissions = frappe.get_all(
                    "LMS Assignment Submission",
                    {"member": student.member, "course": ["in", batch_courses]},
                    ["assignment", "status", "assignment_title", "modified"],
                    order_by="modified desc",
                )
            else:
                assignment_submissions = frappe.get_all(
                    "LMS Assignment Submission",
                    {"member": student.member},
                    ["assignment", "status", "assignment_title", "modified"],
                    order_by="modified desc",
                )

            student.enrollments = enrollments
            student.avg_progress = (
                round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
                if enrollments
                else 0
            )
            student.total_courses = len(enrollments)
            student.status = calculate_status(student.avg_progress)
            student.user_image = frappe.db.get_value(
                "User", student.member, "user_image"
            )
            student.quiz_scores = quiz_submissions
            student.quiz_count = len(quiz_submissions)
            student.avg_quiz_score = (
                round(
                    sum(float(q.get("percentage", 0) or 0) for q in quiz_submissions)
                    / len(quiz_submissions),
                    1,
                )
                if quiz_submissions
                else 0
            )
            student.assignment_scores = assignment_submissions
            student.assignment_count = len(assignment_submissions)
            passed_assignments = len(
                [a for a in assignment_submissions if a.status == "Pass"]
            )
            student.assignments_passed = passed_assignments
            student.assignments_total = len(assignment_submissions)

            # Store batch info for this student
            student.batch = batch.title  # Store batch name
            student.batch_name = batch_name  # Store batch ID

            # Track unique students for summary stats only
            if student.member not in seen_students:
                total_progress += student.avg_progress
                student_count_for_avg += 1
                seen_students.add(student.member)

        total_students += len(students)
        batch.students = students
        batches_data.append(batch)

    # DISABLED: Add students enrolled directly in courses (not via batches)
    # Trainers should only see students enrolled through batches
    # if instructor_courses:
    # 	# Create a virtual "Direct Course Enrollments" batch for students not in any batch
    # 	course_enrollments = frappe.get_all(
    # 		"LMS Enrollment",
    # 		{"course": ["in", instructor_courses]},
    # 		["member", "course", "progress"],
    # 	)

    # 	# Group by student
    # 	students_by_member = {}
    # 	for enrollment in course_enrollments:
    # 		if enrollment.member not in students_by_member:
    # 			member_name = frappe.db.get_value("User", enrollment.member, "full_name")
    # 			students_by_member[enrollment.member] = {
    # 				"member": enrollment.member,
    # 				"member_name": member_name or enrollment.member,
    # 				"enrollments": [],
    # 			}

    # 		# Add course details
    # 		course_title = frappe.db.get_value("LMS Course", enrollment.course, "title")
    # 		students_by_member[enrollment.member]["enrollments"].append({
    # 			"course": enrollment.course,
    # 			"course_title": course_title,
    # 			"progress": enrollment.progress,
    # 			"status": calculate_status(cint(enrollment.progress)),
    # 		})

    # 	# Create students list for direct enrollments
    # 	direct_students = []
    # 	for member, student_data in students_by_member.items():
    # 		# Skip if already in a batch
    # 		if member in seen_students:
    # 			continue

    # 		student = student_data
    # 		enrollments = student["enrollments"]
    # 		student["avg_progress"] = (
    # 			round(sum(cint(e["progress"]) for e in enrollments) / len(enrollments), 1)
    # 			if enrollments
    # 			else 0
    # 		)
    # 		student["total_courses"] = len(enrollments)
    # 		student["status"] = calculate_status(student["avg_progress"])
    # 		student["user_image"] = frappe.db.get_value("User", member, "user_image")

    # 		# Get quiz scores
    # 		quiz_submissions = frappe.get_all(
    # 			"LMS Quiz Submission",
    # 			{"member": member},
    # 			["quiz", "score", "percentage", "creation"],
    # 			order_by="creation desc",
    # 			limit=5
    # 		)
    # 		for quiz_sub in quiz_submissions:
    # 			quiz_title = frappe.db.get_value("LMS Quiz", quiz_sub.quiz, "title")
    # 			quiz_sub.quiz_title = quiz_title

    # 		# Get assignment scores
    # 		assignment_submissions = frappe.get_all(
    # 			"LMS Assignment Submission",
    # 			{"member": member},
    # 			["assignment", "status", "assignment_title", "modified"],
    # 			order_by="modified desc",
    # 			limit=5
    # 		)

    # 		student["quiz_scores"] = quiz_submissions
    # 		student["quiz_count"] = len(quiz_submissions)
    # 		student["avg_quiz_score"] = (
    # 			round(sum(float(q.get("percentage", 0) or 0) for q in quiz_submissions) / len(quiz_submissions), 1)
    # 			if quiz_submissions
    # 			else 0
    # 		)
    # 		student["assignment_scores"] = assignment_submissions
    # 		student["assignment_count"] = len(assignment_submissions)
    # 		passed_assignments = len([a for a in assignment_submissions if a.status == "Pass"])
    # 		student["assignments_passed"] = passed_assignments
    # 		student["assignments_total"] = len(assignment_submissions)

    # 		direct_students.append(student)
    # 		total_progress += student["avg_progress"]
    # 		student_count_for_avg += 1
    # 		seen_students.add(member)

    # 	# Add virtual batch if there are direct students
    # 	if direct_students:
    # 		total_students += len(direct_students)
    # 		batches_data.append({
    # 			"name": "direct-enrollments",
    # 			"title": "Direct Course Enrollments",
    # 			"start_date": None,
    # 			"end_date": None,
    # 			"students": direct_students,
    # 		})

    # Count pending quiz/assignment submissions from students in YOUR batches only
    if seen_students:
        # Get students in your batches
        student_list = list(seen_students)

        # Count quiz submissions from these students only
        pending_quiz_evaluations = frappe.db.count(
            "LMS Quiz Submission",
            {"member": ["in", student_list]},
        )

        # Count assignment submissions that need grading (status = Submitted or Not Graded)
        pending_assignment_evaluations = frappe.db.count(
            "LMS Assignment Submission",
            {"member": ["in", student_list], "status": ["in", ["Submitted", "Not Graded"]]},
        )

        pending_evaluations = pending_quiz_evaluations + pending_assignment_evaluations
    else:
        pending_evaluations = 0

    # Only actionable courses (those that appear in at least one employee's action button),
    # each carrying just the chapters offered for unlocking, ordered by chapter position.
    actionable_courses = []
    for course_entry in sorted(courses_seen.values(), key=lambda c: (c["title"] or "")):
        course_entry["chapters"] = sorted(
            course_entry["chapters"].values(), key=lambda ch: ch["idx"]
        )
        actionable_courses.append(course_entry)

    return {
        "batches": batches_data,
        "courses": actionable_courses,
        "summary": {
            "total_students": len(seen_students),  # Use unique student count
            "avg_progress": (
                round(total_progress / student_count_for_avg, 1)
                if student_count_for_avg
                else 0
            ),
            "pending_evaluations": pending_evaluations,
        },
    }


@frappe.whitelist()
def get_hr_employees(search="", department="", designation="", start=0, limit=20):
    """HR: Get all employees with LMS data."""
    frappe.only_for("LMS HR")

    filters = {}
    or_filters = {}

    if search:
        or_filters["employee_name"] = ["like", f"%{search}%"]
        or_filters["user_id"] = ["like", f"%{search}%"]
    if department:
        filters["department"] = department
    if designation:
        filters["designation"] = designation

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        or_filters=or_filters if or_filters else None,
        fields=[
            "name",
            "employee_name",
            "user_id",
            "department",
            "designation",
            "reports_to",
            "image",
            "company",
            "status",
        ],
        start=cint(start),
        page_length=cint(limit),
        order_by="employee_name asc",
    )

    for emp in employees:
        if emp.user_id:
            roles = frappe.get_all("Has Role", {"parent": emp.user_id}, pluck="role")
            emp.lms_roles = [
                r
                for r in roles
                if r.startswith("LMS")
                or r in ["Course Creator", "Moderator", "Batch Evaluator"]
            ]
            enrollments = frappe.get_all(
                "LMS Enrollment", {"member": emp.user_id}, ["course", "progress"]
            )
            emp.total_courses = len(enrollments)
            emp.avg_progress = (
                round(sum(cint(e.progress) for e in enrollments) / len(enrollments), 1)
                if enrollments
                else 0
            )
        else:
            emp.lms_roles = []
            emp.total_courses = 0
            emp.avg_progress = 0

        if emp.reports_to:
            emp.manager_name = frappe.db.get_value(
                "Employee", emp.reports_to, "employee_name"
            )
        else:
            emp.manager_name = None

    total_count = frappe.db.count("Employee")

    return {
        "employees": employees,
        "total_count": total_count,
    }


@frappe.whitelist()
def get_hr_filters():
    """Get filter options for HR employee list."""
    frappe.only_for("LMS HR")

    departments = frappe.get_all("Department", pluck="name", order_by="name asc")
    designations = frappe.get_all("Designation", pluck="name", order_by="name asc")
    role_profiles = frappe.get_all(
        "Role Profile",
        filters={"name": ["like", "Jamboree%"]},
        pluck="name",
        order_by="name asc",
    )

    return {
        "departments": departments,
        "designations": designations,
        "role_profiles": role_profiles,
    }


@frappe.whitelist()
def save_employee_lms_role(employee, role_profile):
    """HR: Assign a Jamboree role profile to an employee."""
    frappe.only_for("LMS HR")

    emp = frappe.get_doc("Employee", employee)
    if not emp.user_id:
        frappe.throw("Employee has no linked User account. Please link a User first.")

    user = frappe.get_doc("User", emp.user_id)
    user.role_profile_name = role_profile
    user.save(ignore_permissions=True)
    frappe.clear_cache(user=emp.user_id)

    return {
        "success": True,
        "message": f"Role profile '{role_profile}' assigned to {emp.employee_name}",
    }


@frappe.whitelist()
def export_team_progress(manager_employee_id=None):
    """Export team progress as structured data for CSV download."""
    frappe.only_for(
        ["LMS Manager", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"]
    )

    user_roles = frappe.get_roles(frappe.session.user)
    is_super = "System Manager" in user_roles or "LMS HR" in user_roles

    if is_super and not manager_employee_id:
        reports = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=[
                "name",
                "employee_name",
                "user_id",
                "department",
                "designation",
                "image",
            ],
        )
    else:
        reports = get_direct_reports(manager_employee_id)
    rows = []

    for r in reports:
        if not r.user_id:
            continue

        enrollments = frappe.get_all(
            "LMS Enrollment", {"member": r.user_id}, ["course", "progress"]
        )

        if not enrollments:
            rows.append(
                {
                    "employee": r.employee_name,
                    "department": r.department or "",
                    "designation": r.designation or "",
                    "course": "No courses enrolled",
                    "progress": 0,
                }
            )
            continue

        for e in enrollments:
            course_title = (
                frappe.db.get_value("LMS Course", e.course, "title") or e.course
            )
            rows.append(
                {
                    "employee": r.employee_name,
                    "department": r.department or "",
                    "designation": r.designation or "",
                    "course": course_title,
                    "progress": cint(e.progress),
                }
            )

    return rows


@frappe.whitelist()
def get_employee_detail(employee):
    """Get detailed LMS data for a single employee (for HR view)."""
    frappe.only_for("LMS HR")

    emp = frappe.db.get_value(
        "Employee",
        employee,
        [
            "name",
            "employee_name",
            "user_id",
            "department",
            "designation",
            "reports_to",
            "image",
            "company",
            "date_of_joining",
            "status",
            "gender",
            "date_of_birth",
        ],
        as_dict=True,
    )

    if not emp:
        frappe.throw("Employee not found")

    if emp.reports_to:
        emp.manager_name = frappe.db.get_value(
            "Employee", emp.reports_to, "employee_name"
        )

    if emp.user_id:
        roles = frappe.get_all("Has Role", {"parent": emp.user_id}, pluck="role")
        emp.lms_roles = [
            r
            for r in roles
            if r.startswith("LMS")
            or r in ["Course Creator", "Moderator", "Batch Evaluator"]
        ]

        # Get role profile
        emp.role_profile = frappe.db.get_value("User", emp.user_id, "role_profile_name")

        # Enrollments with progress
        enrollments = frappe.get_all(
            "LMS Enrollment",
            {"member": emp.user_id},
            ["name", "course", "progress", "creation", "modified"],
            order_by="creation desc",
        )
        for enrollment in enrollments:
            enrollment.course_title = frappe.db.get_value(
                "LMS Course", enrollment.course, "title"
            )
            enrollment.status = (
                "Completed"
                if cint(enrollment.progress) >= 100
                else ("In Progress" if cint(enrollment.progress) > 0 else "Not Started")
            )

        emp.enrollments = enrollments

        # Quiz submissions - show all
        emp.quiz_submissions = frappe.get_all(
            "LMS Quiz Submission",
            {"member": emp.user_id},
            ["name", "quiz", "score", "creation"],
            order_by="creation desc",
        )

        # Certificates
        emp.certificates = frappe.get_all(
            "LMS Certificate",
            {"member": emp.user_id},
            ["name", "course", "creation"],
            order_by="creation desc",
        )
    else:
        emp.lms_roles = []
        emp.role_profile = None
        emp.enrollments = []
        emp.quiz_submissions = []
        emp.certificates = []

    return emp


@frappe.whitelist()
def update_employee_manager(employee, reports_to):
    """HR: Update the manager (reports_to) of an employee."""
    frappe.only_for("LMS HR")

    emp = frappe.get_doc("Employee", employee)
    if reports_to and reports_to == employee:
        frappe.throw("An employee cannot report to themselves")

    emp.reports_to = reports_to or None
    emp.save(ignore_permissions=True)
    frappe.db.commit()

    manager_name = None
    if reports_to:
        manager_name = frappe.db.get_value("Employee", reports_to, "employee_name")

    return {
        "success": True,
        "message": f"Manager updated for {emp.employee_name}",
        "manager_name": manager_name,
    }


@frappe.whitelist()
def create_employee(
    employee_name,
    gender=None,
    date_of_birth=None,
    user_email=None,
    department=None,
    designation=None,
    reports_to=None,
    company=None,
    date_of_joining=None,
    role_profile=None,
    create_user=0,
):
    """HR: Create a new employee and optionally create a User account + assign role profile."""
    frappe.only_for("LMS HR")

    if not employee_name:
        frappe.throw("Employee name is required")

    create_user = cint(create_user)

    # Get default company
    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        companies = frappe.get_all("Company", limit=1, pluck="name")
        company = companies[0] if companies else None
    if not company:
        frappe.throw("No company found. Please specify a company.")

    # Handle user creation/linking
    actual_user_id = None
    user_created = False
    if user_email:
        if frappe.db.exists("User", user_email):
            actual_user_id = user_email
        elif create_user:
            # Create new User account
            name_parts = employee_name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            new_user = frappe.new_doc("User")
            new_user.email = user_email
            new_user.first_name = first_name
            new_user.last_name = last_name
            new_user.enabled = 1
            new_user.send_welcome_email = 0
            new_user.new_password = frappe.generate_hash(length=12)
            # Attach a role before save so frappe's check_roles_added() does not
            # fire the "Newly created user has no roles enabled" msgprint, which
            # gets surfaced to the LMS frontend and makes the user think the
            # create-employee call failed.
            if role_profile and frappe.db.exists("Role Profile", role_profile):
                new_user.role_profile_name = role_profile
            else:
                new_user.append("roles", {"role": "LMS Student"})
            # Hard-suppress the welcome email regardless of what
            # send_welcome_email ends up being. A site-level Server Script on
            # User.before_insert forces send_welcome_email=1, which then tries
            # to send via the default Email Account; on sites whose
            # encryption_key has rotated this throws "Failed to decrypt key
            # Email Account.No Reply.password" and aborts the whole save.
            new_user.flags.no_welcome_mail = True
            new_user.save(ignore_permissions=True)
            actual_user_id = user_email
            user_created = True
        else:
            frappe.throw(
                f"User {user_email} does not exist. Check 'Create user account' to create one."
            )

    emp = frappe.new_doc("Employee")
    emp.employee_name = employee_name
    name_parts = employee_name.strip().split(" ", 1)
    emp.first_name = name_parts[0]
    if len(name_parts) > 1:
        emp.last_name = name_parts[1]
    emp.company = company
    emp.status = "Active"
    emp.gender = gender or "Male"
    emp.date_of_birth = date_of_birth or "1990-01-01"

    if actual_user_id:
        emp.user_id = actual_user_id

    if department:
        emp.department = department
    if designation:
        emp.designation = designation
    if reports_to:
        emp.reports_to = reports_to
    if date_of_joining:
        emp.date_of_joining = date_of_joining
    else:
        from frappe.utils import today

        emp.date_of_joining = today()

    emp.save(ignore_permissions=True)
    frappe.db.commit()

    # Assign role profile if specified and user exists
    if (
        role_profile
        and actual_user_id
        and frappe.db.exists("Role Profile", role_profile)
    ):
        from lms.lms.custom.jamboree_setup import assign_role_profile_to_user

        assign_role_profile_to_user(actual_user_id, role_profile)

    msg = f"Employee '{employee_name}' created successfully"
    if user_created:
        msg += f" with new user account ({user_email})"

    return {
        "success": True,
        "employee": emp.name,
        "user_created": user_created,
        "message": msg,
    }


@frappe.whitelist()
def get_employee_options():
    """Get all active employees for dropdowns (manager selection)."""
    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name"],
        order_by="employee_name asc",
        limit_page_length=0,
    )
    return employees


@frappe.whitelist()
def update_employee(
    employee,
    employee_name=None,
    gender=None,
    date_of_birth=None,
    date_of_joining=None,
    department=None,
    designation=None,
    reports_to=None,
    user_email=None,
):
    """HR: Update employee details."""
    frappe.only_for("LMS HR")

    emp = frappe.get_doc("Employee", employee)

    if employee_name:
        emp.employee_name = employee_name
        name_parts = employee_name.strip().split(" ", 1)
        emp.first_name = name_parts[0]
        emp.last_name = name_parts[1] if len(name_parts) > 1 else ""
    if gender:
        emp.gender = gender
    if date_of_birth:
        emp.date_of_birth = date_of_birth
    if date_of_joining:
        emp.date_of_joining = date_of_joining
    if department is not None:
        emp.department = department or None
    if designation is not None:
        emp.designation = designation or None
    if reports_to is not None:
        emp.reports_to = reports_to or None
    if user_email is not None:
        if user_email and frappe.db.exists("User", user_email):
            emp.user_id = user_email
        elif not user_email:
            emp.user_id = None

    emp.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "message": f"Employee '{emp.employee_name}' updated successfully",
    }


@frappe.whitelist()
def unassign_employee_course(enrollment):
    """HR: Remove a course enrollment for an employee."""
    frappe.only_for("LMS HR")

    if not frappe.db.exists("LMS Enrollment", enrollment):
        frappe.throw("Enrollment not found.")

    course = frappe.db.get_value("LMS Enrollment", enrollment, "course")
    frappe.delete_doc("LMS Enrollment", enrollment, ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": f"Course '{course}' enrollment removed."}


@frappe.whitelist()
def unassign_employee_role(employee):
    """HR: Remove the LMS role profile from an employee's user account."""
    frappe.only_for("LMS HR")

    emp = frappe.get_doc("Employee", employee)
    if not emp.user_id:
        frappe.throw("Employee has no linked User account.")

    user = frappe.get_doc("User", emp.user_id)
    old_profile = user.role_profile_name
    user.role_profile_name = None
    user.save(ignore_permissions=True)
    frappe.clear_cache(user=emp.user_id)

    # Removing the LMS role profile revokes LMS access — notify HR, the
    # immediate manager and the master trainer(s).
    from lms.lms.custom.notifications import notify_lms_access_revoked

    notify_lms_access_revoked(
        emp.name, reason=f"The LMS role profile '{old_profile}' was removed."
    )

    return {
        "success": True,
        "message": f"Role profile '{old_profile}' removed from {emp.employee_name}",
    }


@frappe.whitelist()
def deactivate_employee(employee, status="Inactive", relieving_date=None):
    """HR: Deactivate an employee (Inactive or Left)."""
    frappe.only_for("LMS HR")

    from frappe.utils import today

    if status not in ("Inactive", "Left"):
        frappe.throw("Invalid status. Choose 'Inactive' or 'Left'.")

    emp = frappe.get_doc("Employee", employee)
    if emp.status == status:
        frappe.throw(f"Employee '{emp.employee_name}' is already {status}.")

    emp.status = status
    if status == "Left":
        emp.relieving_date = relieving_date or today()

    emp.save(ignore_permissions=True)
    frappe.db.commit()

    # Disable the linked user account
    if emp.user_id and frappe.db.exists("User", emp.user_id):
        frappe.db.set_value("User", emp.user_id, "enabled", 0)
        frappe.clear_cache(user=emp.user_id)

    return {
        "success": True,
        "message": f"Employee '{emp.employee_name}' has been set to {status}.",
    }


@frappe.whitelist()
def reactivate_employee(employee):
    """HR: Reactivate an employee (set status to Active)."""
    frappe.only_for("LMS HR")

    emp = frappe.get_doc("Employee", employee)

    # Re-enable the linked user FIRST before saving employee
    if emp.user_id and frappe.db.exists("User", emp.user_id):
        frappe.db.set_value("User", emp.user_id, "enabled", 1)
        frappe.clear_cache(user=emp.user_id)

    emp.status = "Active"
    emp.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "message": f"Employee '{emp.employee_name}' has been reactivated.",
    }


def calculate_status(avg_progress):
    """Calculate student status based on progress."""
    if avg_progress == 0:
        return "Not Started"
    if avg_progress >= 100:
        return "Completed"
    if avg_progress >= 50:
        return "On Track"
    return "Behind"


@frappe.whitelist()
def download_employee_template():
    """Download Excel template for bulk employee upload."""
    import openpyxl
    from openpyxl import Workbook
    from io import BytesIO

    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Employee Template"

    # Headers
    headers = [
        "Employee Name*",
        "Gender*",
        "Date of Birth* (YYYY-MM-DD)",
        "Date of Joining (YYYY-MM-DD)",
        "Email",
        "Department",
        "Designation",
        "Manager Employee ID",
        "Role Profile",
    ]

    # Sample data
    data = [
        [
            "John Doe",
            "Male",
            "1990-01-15",
            "2023-01-01",
            "john.doe@example.com",
            "Sales",
            "Sales Manager",
            "",
            "LMS Student",
        ],
        [
            "Jane Smith",
            "Female",
            "1992-05-20",
            "2023-02-01",
            "jane.smith@example.com",
            "Marketing",
            "Marketing Executive",
            "",
            "LMS Student",
        ],
    ]

    # Write headers
    ws.append(headers)

    # Write sample data
    for row in data:
        ws.append(row)

    # Style headers
    from openpyxl.styles import Font, PatternFill

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            start_color="D3D3D3", end_color="D3D3D3", fill_type="solid"
        )

    # Save to BytesIO
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    frappe.response["filename"] = "employee_bulk_upload_template.xlsx"
    frappe.response["filecontent"] = file_stream.read()
    frappe.response["type"] = "binary"


@frappe.whitelist()
def bulk_upload_employees():
    """Bulk upload employees from Excel/CSV file."""
    import openpyxl
    import csv
    from datetime import datetime

    frappe.only_for(["LMS HR", "System Manager", "LMS Manager"])

    if not frappe.request.files:
        frappe.throw("No file uploaded")

    file = frappe.request.files.get("file")
    if not file:
        frappe.throw("No file found in request")

    filename = file.filename.lower()
    results = {"success": 0, "failed": 0, "errors": []}

    try:
        if filename.endswith((".xlsx", ".xls")):
            # Handle Excel file
            workbook = openpyxl.load_workbook(file)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []

        elif filename.endswith(".csv"):
            # Handle CSV file
            file.stream.seek(0)
            content = file.stream.read().decode("utf-8")
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
        else:
            frappe.throw(
                "Invalid file type. Please upload Excel (.xlsx, .xls) or CSV file"
            )

        # Process each row
        for idx, row in enumerate(data_rows, start=2):
            if not row or not any(row):  # Skip empty rows
                continue

            try:
                # Map columns (adjust based on template)
                employee_name = (
                    str(row[0]).strip()
                    if len(row) > 0 and row[0] and str(row[0]).strip() != "None"
                    else ""
                )
                gender = (
                    str(row[1]).strip()
                    if len(row) > 1 and row[1] and str(row[1]).strip() != "None"
                    else ""
                )
                dob = (
                    str(row[2]).strip()
                    if len(row) > 2 and row[2] and str(row[2]).strip() != "None"
                    else ""
                )
                doj = (
                    str(row[3]).strip()
                    if len(row) > 3 and row[3] and str(row[3]).strip() != "None"
                    else ""
                )
                email = (
                    str(row[4]).strip()
                    if len(row) > 4 and row[4] and str(row[4]).strip() != "None"
                    else ""
                )
                department = (
                    str(row[5]).strip()
                    if len(row) > 5 and row[5] and str(row[5]).strip() != "None"
                    else ""
                )
                designation = (
                    str(row[6]).strip()
                    if len(row) > 6 and row[6] and str(row[6]).strip() != "None"
                    else ""
                )
                reports_to = (
                    str(row[7]).strip()
                    if len(row) > 7 and row[7] and str(row[7]).strip() != "None"
                    else ""
                )
                role_profile = (
                    str(row[8]).strip()
                    if len(row) > 8 and row[8] and str(row[8]).strip() != "None"
                    else ""
                )

                # Validate required fields
                if not employee_name or employee_name == "None":
                    results["errors"].append(f"Row {idx}: Employee name is required")
                    results["failed"] += 1
                    continue

                if not gender or gender not in ["Male", "Female", "Other"]:
                    results["errors"].append(
                        f"Row {idx}: Valid gender is required (Male/Female/Other)"
                    )
                    results["failed"] += 1
                    continue

                if not dob:
                    results["errors"].append(f"Row {idx}: Date of birth is required")
                    results["failed"] += 1
                    continue

                # Parse dates
                try:
                    if isinstance(dob, datetime):
                        dob = dob.strftime("%Y-%m-%d")
                    elif "-" in str(dob):
                        dob = str(dob).split()[0]  # Remove time if present

                    if doj and isinstance(doj, datetime):
                        doj = doj.strftime("%Y-%m-%d")
                    elif doj and "-" in str(doj):
                        doj = str(doj).split()[0]
                except:
                    results["errors"].append(f"Row {idx}: Invalid date format")
                    results["failed"] += 1
                    continue

                # Check if employee with same email already exists
                existing_employee = None
                if email:
                    existing_employee = frappe.db.get_value(
                        "Employee", {"user_id": email}, "name"
                    )

                if existing_employee:
                    results["errors"].append(
                        f"Row {idx}: Employee with email {email} already exists ({existing_employee})"
                    )
                    results["failed"] += 1
                    continue

                # Create employee
                doc = frappe.get_doc(
                    {
                        "doctype": "Employee",
                        "employee_name": employee_name,
                        "gender": gender,
                        "date_of_birth": dob,
                        "date_of_joining": doj or None,
                        "company": frappe.defaults.get_user_default("Company")
                        or frappe.db.get_single_value(
                            "Global Defaults", "default_company"
                        ),
                        "status": "Active",
                        "department": department or None,
                        "designation": designation or None,
                        "reports_to": reports_to or None,
                    }
                )

                # First, try to create/link user if email provided
                if email:
                    existing_user = frappe.db.exists("User", email)
                    if existing_user:
                        doc.user_id = email
                    else:
                        # Create user BEFORE creating employee
                        try:
                            # Split name properly
                            name_parts = [
                                part for part in employee_name.split() if part
                            ]
                            first_name = name_parts[0] if name_parts else "User"
                            last_name = (
                                " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                            )

                            # Validate first_name is not empty
                            if not first_name or first_name.strip() == "":
                                first_name = "User"

                            # Debug logging
                            frappe.log_error(
                                f"Creating user: email={email}, first_name='{first_name}', last_name='{last_name}', employee_name='{employee_name}'",
                                "Bulk Upload Debug",
                            )

                            user_payload = {
                                "doctype": "User",
                                "email": email,
                                "first_name": first_name[
                                    :140
                                ],  # Frappe field limit
                                "last_name": last_name[:140] if last_name else "",
                                "send_welcome_email": 0,
                                "enabled": 1,
                            }
                            # Attach a role before save so frappe's
                            # check_roles_added() does not fire the "no roles
                            # enabled" msgprint into the bulk-upload response.
                            if role_profile and frappe.db.exists(
                                "Role Profile", role_profile
                            ):
                                user_payload["role_profile_name"] = role_profile
                            else:
                                user_payload["roles"] = [{"role": "LMS Student"}]
                            user = frappe.get_doc(user_payload)
                            # See create_employee() for context: a site Server
                            # Script forces send_welcome_email=1, which tries to
                            # send mail through an Email Account whose password
                            # cannot be decrypted, aborting the row.
                            user.flags.no_welcome_mail = True
                            user.insert(ignore_permissions=True)
                            doc.user_id = email
                        except Exception as e:
                            # If user creation fails, don't create employee
                            import traceback

                            error_msg = str(e)
                            full_error = traceback.format_exc()
                            frappe.log_error(
                                f"Bulk Upload User Creation Error Row {idx}", full_error
                            )
                            results["errors"].append(
                                f"Row {idx}: User creation failed for '{employee_name}' (email: {email}) - {error_msg}"
                            )
                            results["failed"] += 1
                            frappe.db.rollback()  # Rollback user creation attempt
                            continue  # Skip employee creation

                # Now create employee (only if user creation succeeded or no email provided)
                doc.insert(ignore_permissions=True)

                # Assign role profile if provided
                if role_profile and doc.user_id:
                    try:
                        role_doc = frappe.get_doc("Role Profile", role_profile)
                        for role in role_doc.roles:
                            if not frappe.db.exists(
                                "Has Role", {"parent": doc.user_id, "role": role.role}
                            ):
                                frappe.get_doc(
                                    {
                                        "doctype": "Has Role",
                                        "parent": doc.user_id,
                                        "parenttype": "User",
                                        "parentfield": "roles",
                                        "role": role.role,
                                    }
                                ).insert(ignore_permissions=True)
                    except:
                        pass

                # Commit all changes for this row
                frappe.db.commit()
                results["success"] += 1

            except Exception as e:
                results["errors"].append(f"Row {idx}: {str(e)}")
                results["failed"] += 1
                frappe.db.rollback()  # Rollback this row's changes

    except Exception as e:
        frappe.db.rollback()
        frappe.throw(f"Error processing file: {str(e)}")

    return results


@frappe.whitelist()
def get_quiz_analytics(quiz_id):
    """Get detailed quiz analytics: attempts, scores, question performance, pass/fail"""
    frappe.only_for(
        ["LMS Trainer", "LMS Master Trainer", "LMS HR", "System Manager", "Moderator"]
    )

    if not frappe.db.exists("LMS Quiz", quiz_id):
        frappe.throw(_("Quiz not found"))

    quiz = frappe.get_doc("LMS Quiz", quiz_id)

    # Get all submissions for this quiz
    submissions = frappe.get_all(
        "LMS Quiz Submission",
        {"quiz": quiz_id},
        ["name", "member", "score", "percentage", "creation"],
        order_by="creation desc",
    )

    for sub in submissions:
        sub.member_name = frappe.db.get_value("User", sub.member, "full_name")
        sub.member_image = frappe.db.get_value("User", sub.member, "user_image")

    # Calculate statistics
    total_attempts = len(submissions)
    if total_attempts > 0:
        avg_score = round(
            sum(s.get("percentage", 0) or 0 for s in submissions) / total_attempts, 1
        )
        max_score = max((s.get("percentage", 0) or 0 for s in submissions), default=0)
        min_score = min((s.get("percentage", 0) or 0 for s in submissions), default=0)
        passed = len(
            [
                s
                for s in submissions
                if (s.get("percentage", 0) or 0) >= (quiz.passing_percentage or 70)
            ]
        )
        failed = total_attempts - passed
    else:
        avg_score = max_score = min_score = passed = failed = 0

    # Score distribution (0-20, 21-40, 41-60, 61-80, 81-100)
    score_ranges = {
        "0-20": 0,
        "21-40": 0,
        "41-60": 0,
        "61-80": 0,
        "81-100": 0,
    }
    for sub in submissions:
        score = sub.get("percentage", 0) or 0
        if score <= 20:
            score_ranges["0-20"] += 1
        elif score <= 40:
            score_ranges["21-40"] += 1
        elif score <= 60:
            score_ranges["41-60"] += 1
        elif score <= 80:
            score_ranges["61-80"] += 1
        else:
            score_ranges["81-100"] += 1

    # Question-wise performance (if questions available)
    question_performance = []
    if hasattr(quiz, "questions") and quiz.questions:
        for q in quiz.questions:
            # Get correct answers count for this question across all submissions
            correct_count = 0
            total_answered = 0

            # This would require storing individual question responses
            # For now, we'll just show the question
            question_performance.append(
                {
                    "question": q.question,
                    "type": q.type,
                    "marks": q.marks,
                    "correct_rate": 0,  # To be calculated if answer data available
                }
            )

    return {
        "quiz_title": quiz.title,
        "quiz_id": quiz_id,
        "summary": {
            "total_attempts": total_attempts,
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "passed": passed,
            "failed": failed,
            "pass_rate": (
                round((passed / total_attempts * 100), 1) if total_attempts > 0 else 0
            ),
        },
        "score_distribution": score_ranges,
        "submissions": submissions,
        "question_performance": question_performance,
    }


@frappe.whitelist()
def get_locked_chapters_for_employee(employee, batch):
    """Get list of locked chapters for an employee in a specific batch

    Args:
        employee: Employee ID or user email
        batch: Batch ID to filter courses by batch (required)
    """

    if not batch:
        frappe.throw("Batch is required")

    # Check if employee is an email (user) or Employee ID
    if "@" in employee:
        # It's a user email
        user_id = employee
    else:
        # It's an Employee ID - get user_id
        user_id = frappe.db.get_value("Employee", employee, "user_id")
        if not user_id:
            frappe.throw("Employee has no linked user account")

    # Get courses assigned to this batch
    batch_courses = frappe.get_all(
        "Batch Course", {"parent": batch}, ["course"], pluck="course"
    )

    if not batch_courses:
        return []

    # Filter enrollments to only batch courses
    enrollments = frappe.get_all(
        "LMS Enrollment",
        filters={"member": user_id, "course": ["in", batch_courses]},
        fields=["course"],
        pluck="course",
    )

    if not enrollments:
        return []

    # Reuse the shared helper so this dropdown and the dashboard's Course/Chapter filters
    # are always computed identically. See `_get_unlockable_chapters` for the unlock-target
    # vs. display-chapter convention.
    chapter_cache = {}
    sequential_cache = {}
    all_locked_chapters = []

    for course in enrollments:
        course_title = frappe.db.get_value("LMS Course", course, "title")
        chapters = _get_course_chapter_structure(course, chapter_cache)
        all_locked_chapters.extend(
            _get_unlockable_chapters(
                course, user_id, chapters, course_title, sequential_cache
            )
        )

    return all_locked_chapters


def _resolve_employee_user(employee, throw=True):
    """Resolve an Employee ID (or user email) to a user id.

    Returns the user id, or ``None`` when the employee has no linked user and
    ``throw`` is False. With ``throw`` True (single-unlock behaviour) it raises.
    """
    if employee and "@" in employee:
        return employee  # already a user email
    user_id = frappe.db.get_value("Employee", employee, "user_id")
    if not user_id and throw:
        frappe.throw(_("Employee has no linked user account"))
    return user_id


def _unlock_chapter(user_id, course, chapter):
    """Core unlock for one (member, course, chapter): set ``manually_unlocked``.

    No permission check and no commit — callers own those (so a bulk caller checks
    permission once and commits once). Returns a status string:

    * ``"not_enrolled"``     – member isn't enrolled in the course (caller decides)
    * ``"already_unlocked"`` – chapter was already manually unlocked (no-op)
    * ``"unlocked"``         – the chapter was just unlocked

    Identical write semantics to the original single-unlock path, so the bulk
    feature inherits the existing course-structure-lock behaviour unchanged.
    """
    if not frappe.db.exists("LMS Enrollment", {"member": user_id, "course": course}):
        return "not_enrolled"

    progress = frappe.db.get_value(
        "LMS Course Progress",
        {"member": user_id, "course": course, "chapter": chapter},
        ["name", "manually_unlocked"],
        as_dict=True,
    )

    if progress and progress.manually_unlocked:
        return "already_unlocked"  # idempotent: skip needless writes

    if progress:
        progress_doc = frappe.get_doc("LMS Course Progress", progress.name)
        progress_doc.manually_unlocked = 1
        progress_doc.unlocked_by = frappe.session.user
        progress_doc.unlock_date = frappe.utils.now()
        progress_doc.save(ignore_permissions=True)
    else:
        progress_doc = frappe.get_doc(
            {
                "doctype": "LMS Course Progress",
                "member": user_id,
                "course": course,
                "chapter": chapter,
                "manually_unlocked": 1,
                "unlocked_by": frappe.session.user,
                "unlock_date": frappe.utils.now(),
                "status": "Not Started",
            }
        )
        progress_doc.insert(ignore_permissions=True)

    return "unlocked"


@frappe.whitelist()
def unlock_chapter_for_employee(employee, course, chapter):
    """Master Trainer: Manually unlock a specific chapter for an employee

    Args:
        employee: Employee ID or user email
        course: Course name
        chapter: Chapter name
    """
    frappe.only_for(["LMS Master Trainer", "LMS HR", "System Manager"])

    user_id = _resolve_employee_user(employee)

    chapter_title = frappe.db.get_value("Course Chapter", chapter, "title")
    if not chapter_title:
        frappe.throw(_("Chapter not found"))

    status = _unlock_chapter(user_id, course, chapter)
    if status == "not_enrolled":
        frappe.throw(_("Employee is not enrolled in this course"))

    frappe.db.commit()  # nosemgrep

    return {
        "success": True,
        "message": f"Chapter '{chapter_title}' unlocked for employee",
        "chapter": chapter,
        "chapter_title": chapter_title,
    }


@frappe.whitelist()
def bulk_unlock_chapter(employees, course, display_chapter):
    """Master Trainer: unlock a filtered chapter for many employees in one action.

    Backs the trainer dashboard's "Unlock selected" bulk action. ``display_chapter`` is
    the dashboard's chapter-filter value — i.e. the *next* chapter shown on the action
    button (see ``_get_unlockable_chapters``), NOT the actual unlock target. For each
    employee we resolve their real unlock target with the same single source of truth
    the per-employee button uses (``_get_unlockable_chapters``), then run the identical
    single-unlock write path. So bulk == repeating the button for each selected employee
    — but with one permission check, one commit, and per-employee outcome reporting.

    Args:
        employees: list of Employee IDs / user emails (JSON string or list).
        course: Course name.
        display_chapter: the chapter-filter value (a ``display_chapter`` / next chapter).

    Returns a summary: employees bucketed by outcome, plus ``counts`` and chapter info.
    """
    frappe.only_for(["LMS Master Trainer", "LMS HR", "System Manager"])

    if isinstance(employees, str):
        employees = frappe.parse_json(employees)
    if not employees:
        frappe.throw(_("No employees selected."))

    course_title = frappe.db.get_value("LMS Course", course, "title")
    if not course_title:
        frappe.throw(_("Course not found"))

    # Resolve the course's chapter structure once; member progress is read per employee
    # inside _get_unlockable_chapters (one query each) — fine for the filtered cohort size.
    chapter_cache, sequential_cache = {}, {}
    course_chapters = _get_course_chapter_structure(course, chapter_cache)

    summary = {
        "unlocked": [],
        "already_unlocked": [],
        "not_enrolled": [],
        "not_offered": [],  # chapter is no longer actionable for this employee (e.g. progressed)
        "errors": [],
    }
    seen = set()
    for employee in employees:
        if employee in seen:
            continue
        seen.add(employee)
        try:
            user_id = _resolve_employee_user(employee, throw=False)
            if not user_id:
                summary["errors"].append({"employee": employee, "reason": "No linked user account"})
                continue

            unlockable = _get_unlockable_chapters(
                course, user_id, course_chapters, course_title, sequential_cache
            )
            match = next(
                (u for u in unlockable if u["display_chapter"] == display_chapter), None
            )
            if not match:
                summary["not_offered"].append(employee)
                continue

            status = _unlock_chapter(user_id, course, match["chapter"])
            summary[status].append(employee)
        except Exception as exc:
            frappe.log_error(title="bulk_unlock_chapter failed for one employee")
            summary["errors"].append({"employee": employee, "reason": str(exc)})

    frappe.db.commit()  # nosemgrep

    summary["counts"] = {key: len(val) for key, val in summary.items() if isinstance(val, list)}
    summary["course"] = course
    summary["display_chapter"] = display_chapter
    return summary
