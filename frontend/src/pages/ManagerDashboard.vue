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
					class="px-4 py-3 bg-surface-gray-1 border-b font-semibold text-ink-gray-9"
				>
					{{ __('Team Learning Progress') }}
				</div>
				<table class="w-full">
					<thead>
						<tr class="border-b text-left text-sm text-ink-gray-5">
							<th class="px-4 py-3 w-8"></th>
							<th class="px-4 py-3">{{ __('Employee') }}</th>
							<th class="px-4 py-3">{{ __('Department') }}</th>
							<th class="px-4 py-3">{{ __('Courses') }}</th>
							<th class="px-4 py-3">{{ __('Completed') }}</th>
							<th class="px-4 py-3">{{ __('Avg Progress') }}</th>
							<th class="px-4 py-3">{{ __('Avg Quiz Score') }}</th>
							<th class="px-4 py-3">{{ __('Assignments') }}</th>
						</tr>
					</thead>
					<tbody>
						<template
							v-for="report in dashboard.data.reports"
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
								<td class="px-4 py-3 text-ink-gray-7">
									{{ report.total_courses }}
								</td>
								<td class="px-4 py-3 text-ink-gray-7">
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
								<td class="px-4 py-3 text-ink-gray-7">
									{{ report.avg_quiz_score || 0 }}%
								</td>
								<td class="px-4 py-3 text-ink-gray-7">
									{{ report.avg_assignment_score || 0 }}%
								</td>
							</tr>
							<!-- Expanded: Course Details -->
							<tr v-if="expandedReport === report.name && report.enrollments?.length">
								<td colspan="8" class="p-0">
									<div class="bg-surface-gray-1">
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
							<tr v-if="expandedReport === report.name && !report.enrollments?.length">
								<td colspan="6" class="p-0">
									<div class="bg-surface-gray-1 px-4 py-3 pl-16 text-sm text-ink-gray-5 border-b">
										{{ __('No course enrollments') }}
									</div>
								</td>
							</tr>
						</template>
					</tbody>
				</table>
			</div>
		</div>
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
} from 'frappe-ui'
import { BarChart3, Download, ChevronRight } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import { ref } from 'vue'

const exporting = ref(false)
const expandedReport = ref(null)

const toggleReport = (name) => {
	expandedReport.value = expandedReport.value === name ? null : name
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
