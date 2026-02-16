<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Trainer Dashboard') },
				]"
			/>
		</header>

		<div class="p-5">
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

			<!-- Batches with Students -->
			<div v-else class="space-y-6">
				<div
					v-for="batch in dashboard.data.batches"
					:key="batch.name"
					class="border rounded-lg"
				>
					<div
						class="px-4 py-3 border-b bg-surface-gray-1 rounded-t-lg"
					>
						<div
							class="flex items-center justify-between"
						>
							<div>
								<h3
									class="font-semibold text-ink-gray-9"
								>
									{{ batch.title }}
								</h3>
								<p
									class="text-sm text-ink-gray-5 mt-0.5"
								>
									{{
										batch.start_date
											? dayjs(
													batch.start_date
												).format('DD MMM YYYY')
											: ''
									}}
									{{
										batch.end_date
											? ' - ' +
												dayjs(
													batch.end_date
												).format('DD MMM YYYY')
											: ''
									}}
								</p>
							</div>
							<Badge
								:label="
									batch.students.length +
									' ' +
									__('students')
								"
								variant="subtle"
								theme="blue"
							/>
						</div>
					</div>

					<div class="divide-y">
						<template
							v-for="student in batch.students"
							:key="student.member"
						>
							<div
								class="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-surface-gray-1 transition-colors"
								@click="toggleStudent(student.member)"
							>
								<div class="flex items-center space-x-3">
									<ChevronRight
										class="size-4 text-ink-gray-4 transition-transform"
										:class="{ 'rotate-90': expandedStudent === student.member }"
									/>
									<UserAvatar
										:user="{
											name: student.member,
											full_name: student.member_name,
											user_image: student.user_image,
										}"
										size="md"
									/>
									<div>
										<div class="font-medium text-ink-gray-9">
											{{ student.member_name }}
										</div>
										<div class="text-sm text-ink-gray-5">
											{{ student.total_courses }} {{ __('courses') }}
										</div>
									</div>
								</div>
								<div class="flex items-center space-x-4">
									<div class="w-32">
										<div class="flex items-center justify-between text-xs text-ink-gray-5 mb-1">
											<span>{{ __('Progress') }}</span>
											<span>{{ student.avg_progress }}%</span>
										</div>
										<div class="w-full bg-surface-gray-2 rounded-full h-2">
											<div
												class="bg-blue-500 h-2 rounded-full transition-all"
												:style="{ width: student.avg_progress + '%' }"
											></div>
										</div>
									</div>
									<Badge
										:label="student.status"
										variant="subtle"
										:theme="getStatusTheme(student.status)"
									/>
								</div>
							</div>
							<!-- Expanded: Course Details -->
							<div
								v-if="expandedStudent === student.member && student.enrollments?.length"
								class="bg-surface-gray-1 border-t"
							>
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
							<div
								v-if="expandedStudent === student.member && !student.enrollments?.length"
								class="bg-surface-gray-1 border-t px-4 py-3 pl-16 text-sm text-ink-gray-5"
							>
								{{ __('No course enrollments') }}
							</div>
						</template>

						<div
							v-if="!batch.students.length"
							class="px-4 py-6 text-center text-ink-gray-5"
						>
							{{ __('No students enrolled in this batch') }}
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Breadcrumbs, createResource, LoadingIndicator, Badge } from 'frappe-ui'
import { GraduationCap, ChevronRight } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import dayjs from 'dayjs'
import { ref } from 'vue'

const expandedStudent = ref(null)

const toggleStudent = (member) => {
	expandedStudent.value = expandedStudent.value === member ? null : member
}

const dashboard = createResource({
	url: 'lms.lms.custom.dashboard_api.get_trainer_dashboard',
	auto: true,
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
</script>
