import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from lms.lms.custom.dashboard_api import (
	get_locked_chapters_for_employee,
	get_trainer_dashboard,
	unlock_chapter_for_employee,
)


class TestUnlockChapter(FrappeTestCase):
	"""Tests for the trainer-dashboard "Unlock Chapter" flow.

	The key invariant under test: the dropdown DISPLAYS the next chapter the student
	gains access to, while the chapter that is actually flagged `manually_unlocked`
	(the identity / unlock target) stays the first incomplete chapter in the sequence.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.student = self.create_user(
			"seq_student@example.com", "Seq", "Student", ["LMS Student"]
		)
		self.course = self.create_sequential_course()
		self.chapters = self.add_chapters(self.course, 3)  # ordered idx 1,2,3
		self.add_lessons(self.course, self.chapters)
		self.batch = self.create_batch(self.course)
		self.enroll(self.course.name, self.student.email)

	# ── helpers ──────────────────────────────────────────────────────────────
	def create_user(self, email, first_name, last_name, roles):
		if frappe.db.exists("User", email):
			return frappe.get_doc("User", email)
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = first_name
		user.last_name = last_name
		user.user_type = "Website User"
		for role in roles:
			user.append("roles", {"role": role})
		user.save()
		return user

	def create_sequential_course(self):
		course = frappe.new_doc("LMS Course")
		course.title = "Sequential Unlock Test Course"
		course.short_introduction = "Course for unlock-chapter tests"
		course.description = "Sequential learning enabled."
		course.published = 1
		course.enable_sequential_learning = 1
		course.append("instructors", {"instructor": "Administrator"})
		course.save()
		return course

	def add_chapters(self, course, count):
		chapters = []
		for i in range(1, count + 1):
			chapter = frappe.new_doc("Course Chapter")
			chapter.course = course.name
			chapter.title = f"Chapter {i}"
			chapter.save()
			chapters.append(chapter)

		course.reload()
		for chapter in chapters:
			course.append("chapters", {"chapter": chapter.name})
		course.save()
		return chapters

	def add_lessons(self, course, chapters):
		content = '{"time":1,"blocks":[{"id":"a","type":"markdown","data":{"text":"x"}}],"version":"2.29.0"}'
		self.lessons = {}  # chapter.name -> [lesson names]
		for chapter in chapters:
			chapter_doc = frappe.get_doc("Course Chapter", chapter.name)
			names = []
			for j in range(1, 3):
				lesson = frappe.new_doc("Course Lesson")
				lesson.course = course.name
				lesson.chapter = chapter.name
				lesson.title = f"Lesson {j} of {chapter.title}"
				lesson.content = content
				lesson.save()
				names.append(lesson.name)
			for lesson_name in names:
				chapter_doc.append("lessons", {"lesson": lesson_name})
			chapter_doc.save()
			self.lessons[chapter.name] = names

	def create_batch(self, course):
		batch = frappe.new_doc("LMS Batch")
		batch.title = "Sequential Unlock Test Batch"
		batch.start_date = nowdate()
		batch.end_date = add_days(nowdate(), 10)
		batch.start_time = "09:00:00"
		batch.end_time = "11:00:00"
		batch.timezone = "Asia/Kolkata"
		batch.description = "Batch for unlock-chapter tests"
		batch.batch_details = "Batch created to test the unlock-chapter flow."
		batch.evaluation_end_date = add_days(nowdate(), 120)
		batch.append("instructors", {"instructor": "Administrator"})
		batch.append("courses", {"course": course.name})
		batch.save()
		return batch

	def enroll(self, course, member):
		enrollment = frappe.new_doc("LMS Enrollment")
		enrollment.course = course
		enrollment.member = member
		enrollment.save()

	def complete_chapter(self, chapter):
		"""Mark every lesson in a chapter Complete for the test student."""
		for lesson_name in self.lessons[chapter.name]:
			frappe.get_doc(
				{
					"doctype": "LMS Course Progress",
					"course": self.course.name,
					"chapter": chapter.name,
					"lesson": lesson_name,
					"member": self.student.email,
					"status": "Complete",
				}
			).insert(ignore_permissions=True)

	# ── tests ────────────────────────────────────────────────────────────────
	def test_display_shows_next_chapter_unlock_targets_first_incomplete(self):
		# Student finished Chapter 1; Chapter 2 is the first incomplete chapter.
		self.complete_chapter(self.chapters[0])

		result = get_locked_chapters_for_employee(
			employee=self.student.email, batch=self.batch.name
		)

		self.assertEqual(len(result), 1)
		entry = result[0]

		# Unlock target (identity fields) = first incomplete chapter = Chapter 2.
		self.assertEqual(entry["chapter"], self.chapters[1].name)
		self.assertEqual(entry["name"], self.chapters[1].name)

		# Display fields = the NEXT chapter the student gains access to = Chapter 3.
		self.assertEqual(entry["title"], "Chapter 3")
		self.assertEqual(entry["chapter_title"], "Chapter 3")
		self.assertEqual(entry["idx"], 3)
		self.assertEqual(entry["display"], f"{self.course.title} - Chapter 3")

	def test_last_chapter_is_not_offered(self):
		# Finish Chapters 1 and 2; Chapter 3 (the last) is the first incomplete.
		# There is no following chapter to grant access to, so nothing is offered and
		# the frontend will show "No locked chapters available to unlock".
		self.complete_chapter(self.chapters[0])
		self.complete_chapter(self.chapters[1])

		result = get_locked_chapters_for_employee(
			employee=self.student.email, batch=self.batch.name
		)

		self.assertEqual(result, [])

	def test_unlock_flags_the_target_chapter(self):
		# The chapter submitted (the unlock target, Chapter 2) is the one flagged.
		self.complete_chapter(self.chapters[0])
		target = self.chapters[1].name

		unlock_chapter_for_employee(
			employee=self.student.email, course=self.course.name, chapter=target
		)

		self.assertEqual(
			frappe.db.get_value(
				"LMS Course Progress",
				{"member": self.student.email, "course": self.course.name, "chapter": target},
				"manually_unlocked",
			),
			1,
		)

		# Once the target is unlocked it is no longer offered again.
		result = get_locked_chapters_for_employee(
			employee=self.student.email, batch=self.batch.name
		)
		self.assertNotIn(target, [r["chapter"] for r in result])

	def tearDown(self):
		# `unlock_chapter_for_employee` calls frappe.db.commit(), which escapes the
		# FrappeTestCase transaction rollback. So clean up explicitly and commit, otherwise
		# the committed rows survive and orphan the course across runs.
		frappe.set_user("Administrator")
		if frappe.db.exists("LMS Batch", self.batch.name):
			frappe.delete_doc("LMS Batch", self.batch.name, force=True)
		frappe.db.delete("LMS Course Progress", {"course": self.course.name})
		frappe.db.delete("LMS Enrollment", {"course": self.course.name})
		frappe.db.delete("Course Lesson", {"course": self.course.name})
		frappe.db.delete("Course Chapter", {"course": self.course.name})
		frappe.db.delete("Course Instructor", {"parent": self.course.name})
		frappe.delete_doc("LMS Course", self.course.name, force=True)
		frappe.delete_doc("User", self.student.email, force=True)
		frappe.db.commit()


class TestTrainerDashboardFilters(FrappeTestCase):
	"""Tests for the Course + Chapter filter enrichment in ``get_trainer_dashboard``.

	The dashboard payload gains a top-level ``courses`` list (to drive the dropdowns) and a
	per-enrollment ``unlocked_chapters`` set used by the chapter filter. A chapter is
	"reached/unlocked" when every previous chapter is complete OR it was manually unlocked;
	for non-sequential courses every chapter counts as reached.

	None of these tests commit, so the FrappeTestCase transaction rolls everything back.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.student = self.create_user(
			"filter_student@example.com", "Filter", "Student", ["LMS Student"]
		)
		# Sequential course: 3 chapters, 2 lessons each.
		self.seq_course = self.create_course("Filter Seq Course", sequential=True)
		self.seq_chapters = self.add_chapters(self.seq_course, 3)
		self.seq_lessons = self.add_lessons(self.seq_course, self.seq_chapters)
		# Non-sequential course: 2 chapters, 2 lessons each.
		self.open_course = self.create_course("Filter Open Course", sequential=False)
		self.open_chapters = self.add_chapters(self.open_course, 2)
		self.add_lessons(self.open_course, self.open_chapters)

		self.batch = self.create_batch([self.seq_course, self.open_course])
		self.batch_enroll(self.batch.name, self.student.email)
		self.enroll(self.seq_course.name, self.student.email)
		self.enroll(self.open_course.name, self.student.email)

	# ── helpers ──────────────────────────────────────────────────────────────
	def create_user(self, email, first_name, last_name, roles):
		if frappe.db.exists("User", email):
			return frappe.get_doc("User", email)
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = first_name
		user.last_name = last_name
		user.user_type = "Website User"
		for role in roles:
			user.append("roles", {"role": role})
		user.save()
		return user

	def create_course(self, title, sequential):
		course = frappe.new_doc("LMS Course")
		course.title = title
		course.short_introduction = "Course for dashboard filter tests"
		course.description = "Dashboard filter test course."
		course.published = 1
		course.enable_sequential_learning = 1 if sequential else 0
		course.append("instructors", {"instructor": "Administrator"})
		course.save()
		return course

	def add_chapters(self, course, count):
		chapters = []
		for i in range(1, count + 1):
			chapter = frappe.new_doc("Course Chapter")
			chapter.course = course.name
			chapter.title = f"Chapter {i}"
			chapter.save()
			chapters.append(chapter)

		course.reload()
		for chapter in chapters:
			course.append("chapters", {"chapter": chapter.name})
		course.save()
		return chapters

	def add_lessons(self, course, chapters):
		content = '{"time":1,"blocks":[{"id":"a","type":"markdown","data":{"text":"x"}}],"version":"2.29.0"}'
		lessons = {}  # chapter.name -> [lesson names]
		for chapter in chapters:
			chapter_doc = frappe.get_doc("Course Chapter", chapter.name)
			names = []
			for j in range(1, 3):
				lesson = frappe.new_doc("Course Lesson")
				lesson.course = course.name
				lesson.chapter = chapter.name
				lesson.title = f"Lesson {j} of {chapter.title}"
				lesson.content = content
				lesson.save()
				names.append(lesson.name)
			for lesson_name in names:
				chapter_doc.append("lessons", {"lesson": lesson_name})
			chapter_doc.save()
			lessons[chapter.name] = names
		return lessons

	def create_batch(self, courses):
		batch = frappe.new_doc("LMS Batch")
		batch.title = "Filter Test Batch"
		batch.start_date = nowdate()
		batch.end_date = add_days(nowdate(), 10)
		batch.start_time = "09:00:00"
		batch.end_time = "11:00:00"
		batch.timezone = "Asia/Kolkata"
		batch.description = "Batch for dashboard filter tests"
		batch.batch_details = "Batch created to test the dashboard filters."
		batch.evaluation_end_date = add_days(nowdate(), 120)
		batch.append("instructors", {"instructor": "Administrator"})
		for course in courses:
			batch.append("courses", {"course": course.name})
		batch.save()
		return batch

	def batch_enroll(self, batch, member):
		enrollment = frappe.new_doc("LMS Batch Enrollment")
		enrollment.batch = batch
		enrollment.member = member
		enrollment.save()

	def enroll(self, course, member):
		enrollment = frappe.new_doc("LMS Enrollment")
		enrollment.course = course
		enrollment.member = member
		enrollment.save()

	def complete_chapter(self, course, chapter, lessons):
		for lesson_name in lessons[chapter.name]:
			frappe.get_doc(
				{
					"doctype": "LMS Course Progress",
					"course": course.name,
					"chapter": chapter.name,
					"lesson": lesson_name,
					"member": self.student.email,
					"status": "Complete",
				}
			).insert(ignore_permissions=True)

	def _enrollment(self, result, course_name):
		"""Pull the test student's enrollment for ``course_name`` out of the payload."""
		for batch in result["batches"]:
			if batch["name"] != self.batch.name:
				continue
			for student in batch["students"]:
				if student["member"] != self.student.email:
					continue
				for enrollment in student["enrollments"]:
					if enrollment["course"] == course_name:
						return enrollment
		return None

	def _course(self, result, course_name):
		return next(
			(c for c in result["courses"] if c["name"] == course_name), None
		)

	# ── tests ────────────────────────────────────────────────────────────────
	# These mirror the "Unlock Chapter" action button: an employee/course/chapter only
	# surfaces when that chapter is currently offered for unlocking. Each entry's *display*
	# chapter (the NEXT chapter the employee gains access to) is what the filter matches.
	def test_courses_list_only_includes_actionable_courses(self):
		# No progress yet: the sequential course offers Chapter 1's unlock (revealing the
		# next chapter), so it is actionable. The non-sequential course never locks, so it
		# is NOT actionable and must be absent from the dropdown source.
		result = get_trainer_dashboard()

		self.assertIsNotNone(self._course(result, self.seq_course.name))
		self.assertIsNone(self._course(result, self.open_course.name))

	def test_action_chapter_is_the_next_chapter_when_nothing_complete(self):
		# First incomplete chapter is Chapter 1 -> the button displays Chapter 2.
		result = get_trainer_dashboard()

		enrollment = self._enrollment(result, self.seq_course.name)
		self.assertEqual(
			enrollment["actionable_chapters"], [self.seq_chapters[1].name]
		)

		# The course's dropdown chapters mirror exactly that displayed chapter.
		course = self._course(result, self.seq_course.name)
		self.assertEqual(
			[c["name"] for c in course["chapters"]], [self.seq_chapters[1].name]
		)
		self.assertEqual(course["chapters"][0]["title"], "Chapter 2")

	def test_completing_a_chapter_advances_the_action_chapter(self):
		# Finish Chapter 1: the first incomplete chapter becomes Chapter 2 -> button now
		# displays Chapter 3.
		self.complete_chapter(self.seq_course, self.seq_chapters[0], self.seq_lessons)

		result = get_trainer_dashboard()
		enrollment = self._enrollment(result, self.seq_course.name)
		self.assertEqual(
			enrollment["actionable_chapters"], [self.seq_chapters[2].name]
		)

	def test_course_drops_off_when_only_last_chapter_remains(self):
		# Finish Chapters 1 and 2: only the last chapter is incomplete, and the last chapter
		# is never offered for unlock -> the course is no longer actionable.
		self.complete_chapter(self.seq_course, self.seq_chapters[0], self.seq_lessons)
		self.complete_chapter(self.seq_course, self.seq_chapters[1], self.seq_lessons)

		result = get_trainer_dashboard()
		self.assertIsNone(self._course(result, self.seq_course.name))
		self.assertEqual(
			self._enrollment(result, self.seq_course.name)["actionable_chapters"], []
		)

	def test_manual_unlock_skips_target_and_advances_action_chapter(self):
		# Manually unlock Chapter 1 (nothing completed). It is skipped without breaking the
		# gate, so Chapter 2 becomes the unlock target and the button displays Chapter 3.
		frappe.get_doc(
			{
				"doctype": "LMS Course Progress",
				"course": self.seq_course.name,
				"chapter": self.seq_chapters[0].name,
				"member": self.student.email,
				"status": "Not Started",
				"manually_unlocked": 1,
			}
		).insert(ignore_permissions=True)

		result = get_trainer_dashboard()
		self.assertEqual(
			self._enrollment(result, self.seq_course.name)["actionable_chapters"],
			[self.seq_chapters[2].name],
		)

	def test_dashboard_filter_matches_unlock_button(self):
		# The dashboard's per-enrollment actionable chapters must equal the chapters the
		# "Unlock Chapter" button would show for the same employee + batch.
		self.complete_chapter(self.seq_course, self.seq_chapters[0], self.seq_lessons)

		result = get_trainer_dashboard()
		dashboard_chapters = set(
			self._enrollment(result, self.seq_course.name)["actionable_chapters"]
		)
		button_chapters = {
			entry["display_chapter"]
			for entry in get_locked_chapters_for_employee(
				employee=self.student.email, batch=self.batch.name
			)
			if entry["course"] == self.seq_course.name
		}
		self.assertEqual(dashboard_chapters, button_chapters)

	def test_non_sequential_course_has_no_actionable_chapters(self):
		result = get_trainer_dashboard()
		enrollment = self._enrollment(result, self.open_course.name)

		self.assertEqual(enrollment["actionable_chapters"], [])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
