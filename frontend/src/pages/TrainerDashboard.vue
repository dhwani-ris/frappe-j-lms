<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Employee Dashboard') },
				]"
			/>
			<div class="flex gap-2 items-center">
				<Button
					variant="subtle"
					:loading="dashboard.loading"
					@click="dashboard.reload()"
				>
					<template #prefix>
						<RotateCw class="size-4 stroke-1.5" />
					</template>
					{{ __('Refresh') }}
				</Button>
				<Button
					variant="subtle"
					@click="router.push({ name: 'Quizzes' })"
				>
					<template #prefix>
						<FileText class="size-4 stroke-1.5" />
					</template>
					{{ __('Quizzes') }}
				</Button>
				<Button
					variant="subtle"
					@click="router.push({ name: 'Assignments' })"
				>
					<template #prefix>
						<ClipboardList class="size-4 stroke-1.5" />
					</template>
					{{ __('Assignments') }}
				</Button>
			</div>
		</header>

		<div class="p-5">
			<!-- Search and Filters -->
			<div v-if="dashboard.data?.batches?.length" class="mb-6 flex flex-wrap gap-3">
				<div class="flex-1 min-w-[250px]">
					<Input
						v-model="searchQuery"
						type="text"
						:placeholder="__('Search students...')"
					>
						<template #prefix>
							<Search class="size-4 text-ink-gray-4" />
						</template>
					</Input>
				</div>
				<FormControl
					type="select"
					v-model="batchFilter"
					:options="batchOptions"
					:placeholder="__('All Batches')"
					class="w-48"
				/>
				<!--
					Native <select> (not frappe-ui FormControl) is used for the course and
					chapter filters on purpose: the chapter option values are Course Chapter
					names containing spaces and parentheses (e.g. "0431 Module 2 (Quiz)"),
					which the reka-ui-based Select mishandles so the v-model never updates.
					A native select binds arbitrary string values reliably.
				-->
				<select
					v-model="courseFilter"
					:aria-label="__('Filter by course')"
					class="w-48 rounded min-h-7 px-2 text-base text-ink-gray-7 border border-outline-gray-2 bg-surface-gray-2 hover:bg-surface-gray-3 transition-colors outline-none focus:ring-2 ring-outline-gray-3"
				>
					<option value="">{{ __('All Courses') }}</option>
					<option
						v-for="c in courseList"
						:key="c.name"
						:value="c.name"
					>
						{{ c.title || c.name }}
					</option>
				</select>
				<select
					v-if="courseFilter"
					v-model="chapterFilter"
					:aria-label="__('Filter by chapter')"
					class="w-48 rounded min-h-7 px-2 text-base text-ink-gray-7 border border-outline-gray-2 bg-surface-gray-2 hover:bg-surface-gray-3 transition-colors outline-none focus:ring-2 ring-outline-gray-3"
				>
					<option value="">{{ __('All Chapters') }}</option>
					<option
						v-for="ch in chapterList"
						:key="ch.name"
						:value="ch.name"
					>
						{{ ch.title }}
					</option>
				</select>
				<FormControl
					type="select"
					v-model="progressFilter"
					:options="progressOptions"
					:placeholder="__('All Progress Levels')"
					class="w-48"
				/>
				<Button
					v-if="hasActiveFilters"
					variant="subtle"
					@click="clearFilters"
				>
					<template #prefix>
						<X class="size-4 stroke-1.5" />
					</template>
					{{ __('Clear Filters') }}
				</Button>
			</div>

			<!-- Summary Cards -->
			<div
				v-if="dashboard.data"
				class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6"
			>
				<div class="border rounded-lg p-4 bg-surface-white">
					<div class="text-sm text-ink-gray-5">
						{{ __('Total Students') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.total_students }}
					</div>
				</div>
				<div class="border rounded-lg p-4 bg-surface-white">
					<div class="text-sm text-ink-gray-5">
						{{ __('Avg Progress') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.avg_progress }}%
					</div>
				</div>
				<div class="border rounded-lg p-4 bg-surface-white">
					<div class="text-sm text-ink-gray-5">
						{{ __('Pending Evaluations') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.pending_evaluations }}
					</div>
				</div>
			</div>

			<!-- Loading State -->
			<div
				v-if="dashboard.loading"
				class="flex items-center justify-center py-20"
			>
				<LoadingIndicator class="size-8" />
			</div>

			<!-- Empty State -->
			<div
				v-else-if="!dashboard.data?.batches?.length"
				class="text-center py-20"
			>
				<GraduationCap
					class="size-12 mx-auto text-ink-gray-4 stroke-1"
				/>
				<p class="mt-3 text-ink-gray-5">
					{{
						__(
							'No batches assigned yet. You will see your students here once you are assigned as an instructor.'
						)
					}}
				</p>
			</div>

			<!-- Students Table -->
			<div v-else class="border rounded-lg overflow-hidden">
				<div
					class="px-4 py-3 bg-surface-gray-1 border-b font-semibold text-ink-gray-9 flex items-center justify-between"
				>
					<span>{{ __('Students Progress') }}</span>
					<span class="text-sm font-normal text-ink-gray-5">
						{{ __('Showing {0} of {1}', [paginatedStudents.length, filteredStudents.length]) }}
					</span>
				</div>
				<table class="w-full">
					<thead>
						<tr class="border-b text-left text-sm text-ink-gray-5">
							<th class="px-4 py-3 w-8"></th>
							<th class="px-4 py-3">{{ __('Student') }}</th>
							<th class="px-4 py-3">{{ __('Batch') }}</th>
							<th class="px-4 py-3 text-center">{{ __('Courses') }}</th>
							<th class="px-4 py-3">{{ __('Avg Progress') }}</th>
							<th class="px-4 py-3 text-center">{{ __('Assessments') }}</th>
							<th class="px-4 py-3 text-center">{{ __('Status') }}</th>
							<th class="px-4 py-3 text-center" v-if="user.data?.is_system_manager || user.data?.is_master_trainer || user.data?.is_lms_hr">{{ __('Actions') }}</th>
						</tr>
					</thead>
					<tbody>
						<template
							v-for="student in paginatedStudents"
							:key="student.member"
						>
							<tr
								class="border-b hover:bg-surface-gray-1 cursor-pointer transition-colors"
								@click="toggleStudent(student.member)"
							>
								<td class="px-4 py-3">
									<ChevronRight
										class="size-4 text-ink-gray-4 transition-transform"
										:class="{ 'rotate-90': expandedStudent === student.member }"
									/>
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center space-x-3">
										<UserAvatar
											:user="{
												name: student.member,
												full_name: student.member_name,
												user_image: student.user_image,
											}"
											size="md"
										/>
										<div>
											<div class="font-medium text-ink-gray-9 cursor-pointer hover:text-blue-600"
												@click.stop="openStudentQuizAnalytics(student)"
											>
												{{ student.member_name }}
											</div>
											<div class="text-xs text-ink-gray-5">
												{{ getAssessmentSummary(student) }}
											</div>
										</div>
									</div>
								</td>
								<td class="px-4 py-3 text-ink-gray-7">
									{{ student.batch_title || '-' }}
								</td>
								<td class="px-4 py-3 text-ink-gray-7 text-center">
									{{ student.total_courses }}
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center space-x-2">
										<div class="w-24 bg-surface-gray-2 rounded-full h-2">
											<div
												class="bg-blue-500 h-2 rounded-full transition-all"
												:style="{ width: student.avg_progress + '%' }"
											></div>
										</div>
										<span class="text-sm text-ink-gray-7">
											{{ student.avg_progress }}%
										</span>
									</div>
								</td>
								<td class="px-4 py-3 text-center">
									<div class="flex flex-col gap-1">
										<div
											class="text-xs cursor-pointer hover:text-blue-600 hover:underline"
											@click.stop="openStudentQuizAnalytics(student)"
										>
											<span class="font-semibold">{{ student.quiz_count || 0 }}</span> {{ __('Quizzes') }}
											<span class="text-ink-gray-5">({{ student.avg_quiz_score || 0 }}%)</span>
										</div>
										<div
											class="text-xs cursor-pointer hover:text-blue-600 hover:underline"
											@click.stop="router.push({ name: 'AssignmentSubmissionList', query: { member: student.member } })"
										>
											<span class="font-semibold">{{ student.assignment_count || 0 }}</span> {{ __('Assignments') }}
										</div>
									</div>
								</td>
								<td class="px-4 py-3 text-center">
									<Badge
										:label="student.status"
										variant="subtle"
										:theme="getStatusTheme(student.status)"
									/>
								</td>
								<td class="px-4 py-3 text-center" v-if="user.data?.is_system_manager || user.data?.is_master_trainer || user.data?.is_lms_hr">
									<Button
										variant="subtle"
										theme="blue"
										size="sm"
										@click.stop="openUnlockChapterModal(student)"
									>
										{{ __('Unlock Chapter') }}
									</Button>
								</td>
							</tr>
							<!-- Expanded: Course Details -->
							<tr v-if="expandedStudent === student.member && student.enrollments?.length">
								<td :colspan="user.data?.is_system_manager || user.data?.is_master_trainer || user.data?.is_lms_hr ? 8 : 7" class="p-0">
									<div class="bg-surface-gray-1">
										<div
											v-for="enrollment in student.enrollments"
											:key="enrollment.course"
											class="px-4 py-2.5 pl-16 flex items-center justify-between border-b last:border-b-0"
										>
											<div class="text-sm text-ink-gray-7">
												{{ enrollment.course_title || enrollment.course }}
											</div>
											<div class="flex items-center space-x-3">
												<div class="w-24">
													<div class="w-full bg-surface-gray-3 rounded-full h-1.5">
														<div
															class="bg-blue-500 h-1.5 rounded-full transition-all"
															:style="{ width: (enrollment.progress || 0) + '%' }"
														></div>
													</div>
												</div>
												<span class="text-xs text-ink-gray-5 w-10 text-right">
													{{ enrollment.progress || 0 }}%
												</span>
												<Badge
													:label="enrollment.status"
													variant="subtle"
													:theme="getStatusTheme(enrollment.status)"
													size="sm"
												/>
											</div>
										</div>
									</div>
								</td>
							</tr>
							<tr v-if="expandedStudent === student.member && !student.enrollments?.length">
								<td :colspan="user.data?.is_system_manager || user.data?.is_master_trainer || user.data?.is_lms_hr ? 8 : 7" class="p-0">
									<div class="bg-surface-gray-1 px-4 py-3 pl-16 text-sm text-ink-gray-5 border-b">
										{{ __('No course enrollments') }}
									</div>
								</td>
							</tr>
						</template>
					</tbody>
				</table>
				<!-- Pagination -->
				<div v-if="filteredStudents.length > perPage" class="px-4 py-3 border-t bg-surface-gray-1 flex items-center justify-between">
					<div class="flex items-center space-x-2">
						<span class="text-sm text-ink-gray-5">{{ __('Show') }}</span>
						<FormControl
							type="select"
							v-model="perPage"
							:options="perPageOptions"
							class="w-20"
						/>
						<span class="text-sm text-ink-gray-5">{{ __('per page') }}</span>
					</div>
					<div class="flex items-center space-x-2">
						<Button
							variant="ghost"
							size="sm"
							:disabled="currentPage === 1"
							@click="currentPage--"
						>
							{{ __('Previous') }}
						</Button>
						<span class="text-sm text-ink-gray-7 px-3">
							{{ __('Page {0} of {1}', [currentPage, totalPages]) }}
						</span>
						<Button
							variant="ghost"
							size="sm"
							:disabled="currentPage === totalPages"
							@click="currentPage++"
						>
							{{ __('Next') }}
						</Button>
					</div>
				</div>
			</div>
		</div>

		<!-- Unlock Chapter Modal -->
		<Dialog
			v-model="showUnlockChapterModal"
			:options="{ title: __('Unlock Chapter') }"
		>
			<template #body-content>
				<div class="space-y-4">
					<div class="text-sm text-gray-700">
						{{ __('Select a chapter to unlock for') }}
						<strong>{{ selectedStudentForUnlock?.member_name }}</strong>
					</div>

					<!-- Chapter Selection -->
					<div v-if="lockedChapters.loading" class="text-sm text-gray-500 py-4 text-center">
						{{ __('Loading...') }}
					</div>
					<div v-else-if="!lockedChapters.data?.length" class="text-sm text-gray-500 py-4 text-center">
						{{ __('No locked chapters available to unlock') }}
					</div>
					<FormControl
						v-else
						v-model="selectedChapterToUnlock"
						type="select"
						:options="unlockChapterOptions"
						:placeholder="__('Select Chapter')"
					/>
				</div>
			</template>
			<template #actions>
				<div class="flex space-x-2">
					<Button variant="subtle" @click="showUnlockChapterModal = false">
						{{ __('Cancel') }}
					</Button>
					<Button
						variant="solid"
						theme="blue"
						:loading="doUnlockChapter.loading"
						:disabled="!selectedChapterToUnlock"
						@click="handleUnlockChapter"
					>
						{{ __('Unlock') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Quiz Analytics Modal -->
		<QuizAnalyticsModal
			v-model="showQuizModal"
			:employee="selectedStudent"
		/>
	</div>
</template>

<script setup>
import { Breadcrumbs, Button, createResource, LoadingIndicator, Badge, Input, FormControl, Dialog, toast } from 'frappe-ui'
import { GraduationCap, ChevronRight, Search, FileText, ClipboardList, BarChart3, X, RotateCw } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import QuizAnalyticsModal from '@/components/QuizAnalyticsModal.vue'
import dayjs from 'dayjs'
import { ref, computed, watch, inject } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = inject('$user')
const expandedStudent = ref(null)
const searchQuery = ref('')
const batchFilter = ref('')
const progressFilter = ref('')
const courseFilter = ref('')
const chapterFilter = ref('')
const currentPage = ref(1)
const perPage = ref(25)
const showQuizModal = ref(false)
const selectedStudent = ref(null)
const showUnlockChapterModal = ref(false)
const selectedStudentForUnlock = ref(null)
const selectedChapterToUnlock = ref('')

const perPageOptions = [
	{ label: '10', value: 10 },
	{ label: '25', value: 25 },
	{ label: '50', value: 50 },
	{ label: '100', value: 100 },
]

const progressOptions = [
	{ label: __('All Progress Levels'), value: '' },
	{ label: __('0-25%'), value: '0-25' },
	{ label: __('25-50%'), value: '25-50' },
	{ label: __('50-75%'), value: '50-75' },
	{ label: __('75-100%'), value: '75-100' },
]

const toggleStudent = (member) => {
	expandedStudent.value = expandedStudent.value === member ? null : member
}

// Reset to page 1 when filters change
watch([searchQuery, batchFilter, progressFilter, courseFilter, chapterFilter], () => {
	currentPage.value = 1
})

// Chapters belong to a course, so reset the chapter filter when the course changes.
watch(courseFilter, () => {
	chapterFilter.value = ''
})

const hasActiveFilters = computed(() => {
	return !!(
		searchQuery.value ||
		batchFilter.value ||
		progressFilter.value ||
		courseFilter.value ||
		chapterFilter.value
	)
})

const clearFilters = () => {
	searchQuery.value = ''
	batchFilter.value = ''
	progressFilter.value = ''
	courseFilter.value = ''
	chapterFilter.value = ''
}

const openStudentQuizAnalytics = (student) => {
	selectedStudent.value = {
		employee_name: student.member_name,
		user_id: student.member,
		quiz_scores: student.quiz_scores || [],
		avg_quiz_score: student.avg_quiz_score || 0,
	}
	showQuizModal.value = true
}

const openQuizAnalytics = (student) => {
	if (!student) return
	openStudentQuizAnalytics(student)
}

const dashboard = createResource({
	url: 'lms.lms.custom.dashboard_api.get_trainer_dashboard',
	auto: true,
})

// Re-fetch the dashboard whenever the chapter filter changes — equivalent to clicking the
// Refresh button right after picking a chapter. Reloading reassigns `dashboard.data`, which
// forces the student list to recompute against the current chapter selection (and pulls the
// latest unlock data on this live site). Guarded so it only runs after the initial load.
watch(chapterFilter, () => {
	if (dashboard.fetched) {
		dashboard.reload()
	}
})

// Computed: Batch options from data
const batchOptions = computed(() => {
	if (!dashboard.data?.batches) return []
	return [
		{ label: __('All Batches'), value: '' },
		...dashboard.data.batches.map(b => ({
			label: b.title,
			value: b.name  // Use batch ID instead of title
		}))
	]
})

// Courses present in the dashboard (only those with an actionable "Unlock Chapter" entry).
const courseList = computed(() => dashboard.data?.courses || [])

// Chapters offered for unlocking in the selected course, ordered by position.
const chapterList = computed(() => {
	const course = dashboard.data?.courses?.find(c => c.name === courseFilter.value)
	if (!course) return []
	return [...course.chapters].sort((a, b) => a.idx - b.idx)
})

// Computed: All students across all batches
const allStudents = computed(() => {
	if (!dashboard.data?.batches) return []

	const students = []
	dashboard.data.batches.forEach(batch => {
		batch.students.forEach(student => {
			students.push({
				...student,
				batch_title: batch.title,
				batch_name: batch.name
			})
		})
	})
	return students
})

// Computed: Filtered students
const filteredStudents = computed(() => {
	// Read every filter ref unconditionally up front so they are ALL registered as reactive
	// dependencies of this computed. (chapterFilter in particular is only used deep inside a
	// conditional below; reading it only there means Vue may not track it, so changing the
	// chapter would not trigger a recompute — the bug that required a manual Refresh.)
	const query = searchQuery.value.toLowerCase()
	const batch = batchFilter.value
	const progress = progressFilter.value
	const course = courseFilter.value
	const chapter = chapterFilter.value

	let filtered = allStudents.value

	// Search filter
	if (query) {
		filtered = filtered.filter(s =>
			s.member_name?.toLowerCase().includes(query) ||
			s.member?.toLowerCase().includes(query) ||
			s.batch_title?.toLowerCase().includes(query)
		)
	}

	// Batch filter
	if (batch) {
		filtered = filtered.filter(s => s.batch_title === batch)
	}

	// Progress filter
	if (progress) {
		const [min, max] = progress.split('-').map(Number)
		filtered = filtered.filter(s => {
			const value = s.avg_progress || 0
			return value >= min && value <= max
		})
	}

	// Course filter (+ dependent chapter filter), driven by the "Unlock Chapter" action
	// button: an employee matches only when the selected course (and chapter) is one they
	// can currently be offered to unlock.
	if (course) {
		filtered = filtered.filter(s => {
			const enrollment = s.enrollments?.find(en => en.course === course)
			const actionable = enrollment?.actionable_chapters || []
			if (!actionable.length) return false
			if (!chapter) return true
			return actionable.includes(chapter)
		})
	}

	return filtered
})

// Computed: Paginated students
const paginatedStudents = computed(() => {
	const start = (currentPage.value - 1) * perPage.value
	const end = start + perPage.value
	return filteredStudents.value.slice(start, end)
})

// Computed: Total pages
const totalPages = computed(() => {
	return Math.ceil(filteredStudents.value.length / perPage.value) || 1
})

const getStatusTheme = (status) => {
	const themes = {
		Completed: 'green',
		'On Track': 'blue',
		Behind: 'orange',
		'Not Started': 'gray',
	}
	return themes[status] || 'gray'
}

const getAssessmentSummary = (student) => {
	const parts = []
	if (student.quiz_count) {
		parts.push(`${student.quiz_count} quiz${student.quiz_count > 1 ? 'zes' : ''}`)
	}
	if (student.assignment_count) {
		parts.push(`${student.assignment_count} assignment${student.assignment_count > 1 ? 's' : ''}`)
	}
	return parts.length ? parts.join(', ') : __('No assessments')
}

// ─── Unlock Chapter ──────────────────────────────────────────────────────────
const lockedChapters = createResource({
	url: 'lms.lms.custom.dashboard_api.get_locked_chapters_for_employee',
	makeParams(values) {
		return {
			employee: values.employee,
			batch: values.batch,
		}
	},
})

const doUnlockChapter = createResource({
	url: 'lms.lms.custom.dashboard_api.unlock_chapter_for_employee',
})

const unlockChapterOptions = computed(() => {
	if (!lockedChapters.data) return []
	return lockedChapters.data.map(chapter => ({
		label: chapter.display,
		value: JSON.stringify({ course: chapter.course, chapter: chapter.chapter })
	}))
})

const openUnlockChapterModal = async (student) => {
	selectedStudentForUnlock.value = student
	selectedChapterToUnlock.value = ''
	showUnlockChapterModal.value = true

	// Fetch locked chapters for this student in their batch
	await lockedChapters.submit({
		employee: student.member,
		batch: student.batch_name,
	})

	// If a course + chapter filter is active, pre-select that exact chapter in the modal so
	// the chapter offered for unlocking matches what the user filtered by. The filter value
	// is the display chapter (the next chapter shown in the button); we map it back to the
	// option whose value carries the actual unlock-target chapter.
	if (courseFilter.value && chapterFilter.value && lockedChapters.data) {
		const match = lockedChapters.data.find(
			(c) =>
				c.course === courseFilter.value &&
				c.display_chapter === chapterFilter.value
		)
		if (match) {
			selectedChapterToUnlock.value = JSON.stringify({
				course: match.course,
				chapter: match.chapter,
			})
		}
	}
}

const handleUnlockChapter = async () => {
	if (!selectedChapterToUnlock.value) {
		toast.error(__('Please select a chapter to unlock'))
		return
	}

	try {
		const { course, chapter } = JSON.parse(selectedChapterToUnlock.value)

		await doUnlockChapter.submit({
			employee: selectedStudentForUnlock.value.member,
			course: course,
			chapter: chapter,
		})
		toast.success(
			doUnlockChapter.data?.message || __('Chapter unlocked successfully')
		)
		showUnlockChapterModal.value = false
		selectedChapterToUnlock.value = ''
		dashboard.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to unlock chapter'))
	}
}
</script>
