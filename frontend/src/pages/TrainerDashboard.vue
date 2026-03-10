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
			<div class="flex gap-2">
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
				<FormControl
					type="select"
					v-model="progressFilter"
					:options="progressOptions"
					:placeholder="__('All Progress Levels')"
					class="w-48"
				/>
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
							</tr>
							<!-- Expanded: Course Details -->
							<tr v-if="expandedStudent === student.member && student.enrollments?.length">
								<td colspan="7" class="p-0">
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
								<td colspan="7" class="p-0">
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

		<!-- Quiz Analytics Modal -->
		<QuizAnalyticsModal
			v-model="showQuizModal"
			:employee="selectedStudent"
		/>
	</div>
</template>

<script setup>
import { Breadcrumbs, Button, createResource, LoadingIndicator, Badge, Input, FormControl } from 'frappe-ui'
import { GraduationCap, ChevronRight, Search, FileText, ClipboardList, BarChart3 } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import QuizAnalyticsModal from '@/components/QuizAnalyticsModal.vue'
import dayjs from 'dayjs'
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const expandedStudent = ref(null)
const searchQuery = ref('')
const batchFilter = ref('')
const progressFilter = ref('')
const currentPage = ref(1)
const perPage = ref(25)
const showQuizModal = ref(false)
const selectedStudent = ref(null)

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
watch([searchQuery, batchFilter, progressFilter], () => {
	currentPage.value = 1
})

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

// Computed: Batch options from data
const batchOptions = computed(() => {
	if (!dashboard.data?.batches) return []
	const batches = dashboard.data.batches.map(b => b.title).filter(Boolean)
	return [
		{ label: __('All Batches'), value: '' },
		...batches.map(b => ({ label: b, value: b }))
	]
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
	let filtered = allStudents.value

	// Search filter
	if (searchQuery.value) {
		const query = searchQuery.value.toLowerCase()
		filtered = filtered.filter(s =>
			s.member_name?.toLowerCase().includes(query) ||
			s.member?.toLowerCase().includes(query) ||
			s.batch_title?.toLowerCase().includes(query)
		)
	}

	// Batch filter
	if (batchFilter.value) {
		filtered = filtered.filter(s => s.batch_title === batchFilter.value)
	}

	// Progress filter
	if (progressFilter.value) {
		const [min, max] = progressFilter.value.split('-').map(Number)
		filtered = filtered.filter(s => {
			const progress = s.avg_progress || 0
			return progress >= min && progress <= max
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
</script>
