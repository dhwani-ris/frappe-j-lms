<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Manager Dashboard') },
				]"
			/>
			<Button
				v-if="dashboard.data?.reports?.length"
				variant="subtle"
				@click="exportCSV"
				:loading="exporting"
			>
				<template #prefix>
					<Download class="size-4 stroke-1.5" />
				</template>
				{{ __('Export CSV') }}
			</Button>
		</header>

		<div class="p-5">
			<!-- Employee feedback awaiting this manager -->
			<EmployeeFeedbackList :heading="__('Employee Feedback')" role="manager" />

			<!-- Search and Filters -->
			<div v-if="dashboard.data?.reports?.length" class="mb-6 flex flex-wrap gap-3">
				<div class="flex-1 min-w-[250px]">
					<Input
						v-model="searchQuery"
						type="text"
						:placeholder="__('Search employees...')"
					>
						<template #prefix>
							<Search class="size-4 text-ink-gray-4" />
						</template>
					</Input>
				</div>
				<FormControl
					type="select"
					v-model="departmentFilter"
					:options="departmentOptions"
					:placeholder="__('All Departments')"
					class="w-48"
				/>
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
						{{ __('Team Size') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.team_size }}
					</div>
				</div>
				<div class="border rounded-lg p-4 bg-surface-white">
					<div class="text-sm text-ink-gray-5">
						{{ __('Avg Team Progress') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.avg_progress }}%
					</div>
				</div>
				<div class="border rounded-lg p-4 bg-surface-white">
					<div class="text-sm text-ink-gray-5">
						{{ __('Completed Courses') }}
					</div>
					<div class="text-2xl font-bold text-ink-gray-9 mt-1">
						{{ dashboard.data.summary.total_completed }}
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
				v-else-if="!dashboard.data?.reports?.length"
				class="text-center py-20"
			>
				<BarChart3
					class="size-12 mx-auto text-ink-gray-4 stroke-1"
				/>
				<p class="mt-3 text-ink-gray-5">
					{{
						__(
							'No direct reports found. Team members who report to you will appear here.'
						)
					}}
				</p>
			</div>

			<!-- Team Progress Table -->
			<div v-else class="border rounded-lg overflow-hidden">
				<div
					class="px-4 py-3 bg-surface-gray-1 border-b font-semibold text-ink-gray-9 flex items-center justify-between"
				>
					<span>{{ __('Team Learning Progress') }}</span>
					<span class="text-sm font-normal text-ink-gray-5">
						{{ __('Showing {0} of {1}', [paginatedReports.length, filteredReports.length]) }}
					</span>
				</div>
				<table class="w-full">
					<thead>
						<tr class="border-b text-left text-sm text-ink-gray-5">
							<th class="px-4 py-3 w-8"></th>
							<th class="px-4 py-3">{{ __('Employee') }}</th>
							<th class="px-4 py-3">{{ __('Department') }}</th>
							<th class="px-4 py-3 text-center">{{ __('Courses') }}</th>
							<th class="px-4 py-3 text-center">{{ __('Completed') }}</th>
							<th class="px-4 py-3">{{ __('Avg Progress') }}</th>
							<th class="px-4 py-3 text-center cursor-pointer hover:text-ink-gray-9" @click="openQuizAnalytics">
								{{ __('Quiz Score') }}
								<BarChart3 class="inline size-3 ml-1" />
							</th>
							<th class="px-4 py-3 text-center">{{ __('Assignments') }}</th>
						</tr>
					</thead>
					<tbody>
						<template
							v-for="report in paginatedReports"
							:key="report.name"
						>
							<tr
								class="border-b hover:bg-surface-gray-1 cursor-pointer transition-colors"
								@click="toggleReport(report.name)"
							>
								<td class="px-4 py-3">
									<ChevronRight
										class="size-4 text-ink-gray-4 transition-transform"
										:class="{ 'rotate-90': expandedReport === report.name }"
									/>
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center space-x-3">
										<UserAvatar
											:user="{
												name: report.user_id,
												full_name: report.employee_name,
												user_image: report.image,
											}"
											size="md"
										/>
										<div>
											<div class="font-medium text-ink-gray-9">
												{{ report.employee_name }}
											</div>
											<div class="text-xs text-ink-gray-5">
												{{ report.designation || '' }}
											</div>
										</div>
									</div>
								</td>
								<td class="px-4 py-3 text-ink-gray-7">
									{{ report.department || '-' }}
								</td>
								<td class="px-4 py-3 text-ink-gray-7 text-center">
									{{ report.total_courses }}
								</td>
								<td class="px-4 py-3 text-ink-gray-7 text-center">
									{{ report.completed }}
								</td>
								<td class="px-4 py-3">
									<div class="flex items-center space-x-2">
										<div class="w-24 bg-surface-gray-2 rounded-full h-2">
											<div
												class="bg-blue-500 h-2 rounded-full transition-all"
												:style="{ width: report.avg_progress + '%' }"
											></div>
										</div>
										<span class="text-sm text-ink-gray-7">
											{{ report.avg_progress }}%
										</span>
									</div>
								</td>
								<td
									class="px-4 py-3 text-center cursor-pointer hover:text-blue-600 hover:underline"
									@click.stop="openQuizAnalytics(report)"
								>
									<span class="font-semibold">{{ report.avg_quiz_score || 0 }}%</span>
									<span class="text-xs text-ink-gray-5 block">{{ report.quiz_scores?.length || 0 }} quizzes</span>
								</td>
								<td class="px-4 py-3 text-ink-gray-7 text-center">
									{{ report.avg_assignment_score || 0 }}%
								</td>
							</tr>
							<!-- Expanded: Course Details -->
							<tr v-if="expandedReport === report.name && report.enrollments?.length">
								<td colspan="8" class="p-0">
									<div class="bg-surface-gray-1">
										<div class="px-4 pt-3 pb-1 pl-16 text-xs font-semibold uppercase text-ink-gray-4">
											{{ __('Courses') }}
										</div>
										<div
											v-for="enrollment in report.enrollments"
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
													:label="getEnrollmentStatus(enrollment.progress)"
													variant="subtle"
													:theme="getStatusTheme(getEnrollmentStatus(enrollment.progress))"
													size="sm"
												/>
											</div>
										</div>
									</div>
								</td>
							</tr>
							<!-- Expanded: Resource-linked quiz activity, grouped by top-level
								 Resource folder (Resources are a company-wide library, not
								 course content, so this is shown separately from course
								 enrollments above, same distinction Employee Dashboard makes). -->
							<tr v-if="expandedReport === report.name && report.resource_folders?.length">
								<td colspan="8" class="p-0">
									<div class="bg-surface-gray-1">
										<div class="px-4 pt-3 pb-1 pl-16 text-xs font-semibold uppercase text-ink-gray-4">
											{{ __('Resource Quizzes') }}
										</div>
										<div
											v-for="folder in report.resource_folders"
											:key="folder.folder_name"
											class="px-4 py-2.5 pl-16 flex items-center justify-between border-b last:border-b-0"
										>
											<div class="text-sm text-ink-gray-7">
												{{ folder.folder_name }}
											</div>
											<div class="flex items-center space-x-3">
												<span class="text-xs text-ink-gray-5">
													{{ __('{0} Quizzes').format(folder.quiz_count) }}
												</span>
												<Badge
													:label="__('Completed')"
													variant="subtle"
													theme="green"
													size="sm"
												/>
											</div>
										</div>
									</div>
								</td>
							</tr>
							<tr
								v-if="
									expandedReport === report.name &&
									!report.enrollments?.length &&
									!report.resource_folders?.length
								"
							>
								<td colspan="6" class="p-0">
									<div class="bg-surface-gray-1 px-4 py-3 pl-16 text-sm text-ink-gray-5 border-b">
										{{ __('No course enrollments') }}
									</div>
								</td>
							</tr>
						</template>
					</tbody>
				</table>
				<!-- Pagination -->
				<div v-if="filteredReports.length > perPage" class="px-4 py-3 border-t bg-surface-gray-1 flex items-center justify-between">
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
			:employee="selectedEmployee"
		/>
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Button,
	Badge,
	createResource,
	LoadingIndicator,
	call,
	Input,
	FormControl,
} from 'frappe-ui'
import { BarChart3, Download, ChevronRight, Search, X } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import QuizAnalyticsModal from '@/components/QuizAnalyticsModal.vue'
import EmployeeFeedbackList from '@/components/EmployeeFeedbackList.vue'
import { ref, computed, watch } from 'vue'

const exporting = ref(false)
const expandedReport = ref(null)
const searchQuery = ref('')
const departmentFilter = ref('')
const progressFilter = ref('')
const currentPage = ref(1)
const perPage = ref(25)
const showQuizModal = ref(false)
const selectedEmployee = ref(null)

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

const toggleReport = (name) => {
	expandedReport.value = expandedReport.value === name ? null : name
}

const openQuizAnalytics = (report) => {
	if (!report) return
	selectedEmployee.value = report
	showQuizModal.value = true
}

// Reset to page 1 when filters change
watch([searchQuery, departmentFilter, progressFilter], () => {
	currentPage.value = 1
})

const hasActiveFilters = computed(() => {
	return !!(searchQuery.value || departmentFilter.value || progressFilter.value)
})

const clearFilters = () => {
	searchQuery.value = ''
	departmentFilter.value = ''
	progressFilter.value = ''
}

const getEnrollmentStatus = (progress) => {
	const p = progress || 0
	if (p >= 100) return 'Completed'
	if (p > 0) return 'In Progress'
	return 'Not Started'
}

const getStatusTheme = (status) => {
	const themes = {
		Completed: 'green',
		'In Progress': 'blue',
		'On Track': 'blue',
		Behind: 'orange',
		'Not Started': 'gray',
	}
	return themes[status] || 'gray'
}

const dashboard = createResource({
	url: 'lms.lms.custom.dashboard_api.get_manager_dashboard',
	auto: true,
	onSuccess(data) {
		console.log('Manager Dashboard Data:', {
			total_reports: data?.reports?.length || 0,
			team_size: data?.summary?.team_size || 0,
			reports: data?.reports
		})
	}
})

// Computed: Department options from data
const departmentOptions = computed(() => {
	if (!dashboard.data?.reports) return []
	const depts = [...new Set(dashboard.data.reports.map(r => r.department).filter(Boolean))]
	return [
		{ label: __('All Departments'), value: '' },
		...depts.map(d => ({ label: d, value: d }))
	]
})

// Computed: Filtered reports
const filteredReports = computed(() => {
	if (!dashboard.data?.reports) return []

	let filtered = dashboard.data.reports

	// Search filter
	if (searchQuery.value) {
		const query = searchQuery.value.toLowerCase()
		filtered = filtered.filter(r =>
			r.employee_name?.toLowerCase().includes(query) ||
			r.department?.toLowerCase().includes(query) ||
			r.designation?.toLowerCase().includes(query)
		)
	}

	// Department filter
	if (departmentFilter.value) {
		filtered = filtered.filter(r => r.department === departmentFilter.value)
	}

	// Progress filter
	if (progressFilter.value) {
		const [min, max] = progressFilter.value.split('-').map(Number)
		filtered = filtered.filter(r => {
			const progress = r.avg_progress || 0
			return progress >= min && progress <= max
		})
	}

	return filtered
})

// Computed: Paginated reports
const paginatedReports = computed(() => {
	const start = (currentPage.value - 1) * perPage.value
	const end = start + perPage.value
	return filteredReports.value.slice(start, end)
})

// Computed: Total pages
const totalPages = computed(() => {
	return Math.ceil(filteredReports.value.length / perPage.value) || 1
})

const exportCSV = async () => {
	exporting.value = true
	try {
		const data = await call(
			'lms.lms.custom.dashboard_api.export_team_progress'
		)
		if (!data || !data.length) return

		const headers = ['Employee', 'Department', 'Designation', 'Course', 'Progress']
		const csvRows = [headers.join(',')]

		for (const row of data) {
			csvRows.push(
				[
					`"${row.employee}"`,
					`"${row.department}"`,
					`"${row.designation}"`,
					`"${row.course}"`,
					row.progress,
				].join(',')
			)
		}

		const csvContent = csvRows.join('\n')
		const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
		const link = document.createElement('a')
		link.href = URL.createObjectURL(blob)
		link.download = 'team_progress.csv'
		link.click()
	} finally {
		exporting.value = false
	}
}
</script>
