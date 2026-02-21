<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Assign Course') },
				]"
			/>
		</header>

		<div class="p-5 max-w-2xl">
			<!-- Assignment Form -->
			<div class="border rounded-lg p-5 bg-surface-white">
				<h2 class="text-lg font-semibold text-ink-gray-9 mb-4">
					{{ __('Assign Course to Student') }}
				</h2>

				<div class="space-y-4">
					<div>
						<label
							class="block text-sm font-medium text-ink-gray-7 mb-1"
						>
							{{ __('Student') }}
						</label>
						<Autocomplete
							v-model="selectedStudent"
							:options="studentOptions"
							:placeholder="__('Search by name or email...')"
						/>
					</div>

					<div>
						<label
							class="block text-sm font-medium text-ink-gray-7 mb-1"
						>
							{{ __('Course') }}
						</label>
						<Autocomplete
							v-model="selectedCourse"
							:options="courseOptions"
							:placeholder="__('Search for a course...')"
						/>
					</div>

					<div>
						<label
							class="block text-sm font-medium text-ink-gray-7 mb-1"
						>
							{{ __('Trainers') }}
						</label>
						<Autocomplete
							v-model="selectedTrainers"
							:options="trainerOptions"
							:placeholder="__('Select one or more trainers...')"
							:multiple="true"
						/>
						<div class="text-xs text-ink-gray-5 mt-1">
							{{ __('Leave empty to assign yourself as the trainer') }}
						</div>
					</div>

					<div class="grid grid-cols-2 gap-4">
						<div>
							<label
								class="block text-sm font-medium text-ink-gray-7 mb-1"
							>
								{{ __('Start Date') }}
							</label>
							<FormControl
								v-model="startDate"
								type="date"
							/>
						</div>
						<div>
							<label
								class="block text-sm font-medium text-ink-gray-7 mb-1"
							>
								{{ __('End Date') }}
							</label>
							<FormControl
								v-model="endDate"
								type="date"
							/>
						</div>
					</div>

					<Button
						variant="solid"
						:loading="assignResource.loading"
						:disabled="!selectedStudent || !selectedCourse"
						@click="assignCourse"
					>
						{{ __('Assign Course') }}
					</Button>
				</div>
			</div>

			<!-- Recent Assignments -->
			<div class="mt-6">
				<h3 class="text-lg font-semibold text-ink-gray-9 mb-3">
					{{ __('Recent Assignments') }}
				</h3>

				<div
					v-if="recentAssignments.loading"
					class="flex justify-center py-8"
				>
					<LoadingIndicator class="size-6" />
				</div>

				<div
					v-else-if="!recentAssignments.data?.length"
					class="text-center py-8 text-ink-gray-5 border rounded-lg"
				>
					{{ __('No recent assignments') }}
				</div>

				<div v-else class="border rounded-lg divide-y">
					<div
						v-for="assignment in recentAssignments.data"
						:key="assignment.name"
						class="px-4 py-3 flex items-center justify-between"
					>
						<div>
							<div class="font-medium text-ink-gray-9">
								{{ assignment.course_title }}
							</div>
							<div class="text-sm text-ink-gray-5">
								{{ __('Assigned to') }}
								{{ assignment.student_name }}
							</div>
						</div>
						<div class="text-sm text-ink-gray-5">
							{{ dayjs(assignment.creation).format('DD MMM YYYY') }}
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Button,
	Autocomplete,
	FormControl,
	LoadingIndicator,
	createResource,
	toast,
} from 'frappe-ui'
import { ref, computed } from 'vue'
import dayjs from 'dayjs'

const selectedStudent = ref('')
const selectedCourse = ref('')
const selectedTrainers = ref([])
const startDate = ref(dayjs().format('YYYY-MM-DD'))
const endDate = ref(dayjs().add(3, 'month').format('YYYY-MM-DD'))

const allUsers = createResource({
	url: 'lms.lms.api.get_all_users',
	auto: true,
})

const allCourses = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'LMS Course',
		fields: ['name', 'title'],
		filters: { published: 1 },
		limit_page_length: 0,
	},
	auto: true,
})

const recentAssignments = createResource({
	url: 'lms.lms.custom.course_assignment.get_recent_assignments',
	auto: true,
})

const studentOptions = computed(() => {
	if (!allUsers.data) return []
	// Filter to only show students (users with LMS Student role)
	return Object.values(allUsers.data)
		.filter((user) => user.is_student)
		.map((user) => ({
			label: user.full_name || user.name,
			value: user.name,
		}))
})

const courseOptions = computed(() => {
	if (!allCourses.data) return []
	return allCourses.data.map((course) => ({
		label: course.title || course.name,
		value: course.name,
	}))
})

const trainerOptions = computed(() => {
	if (!allUsers.data) return []
	// Filter to only show trainers and master trainers
	return Object.values(allUsers.data)
		.filter((user) => user.is_trainer || user.is_master_trainer)
		.map((user) => ({
			label: user.full_name || user.name,
			value: user.name,
		}))
})

const assignResource = createResource({
	url: 'lms.lms.custom.course_assignment.assign_course_to_student',
})

const assignCourse = async () => {
	if (!selectedStudent.value || !selectedCourse.value) return

	try {
		const trainers = selectedTrainers.value?.length
			? selectedTrainers.value.map(t => t.value)
			: []

		await assignResource.submit({
			student_email: selectedStudent.value.value,
			course: selectedCourse.value.value,
			trainers: trainers,
			start_date: startDate.value,
			end_date: endDate.value,
		})
		toast.success(assignResource.data?.message || __('Course assigned successfully'))
		selectedStudent.value = ''
		selectedCourse.value = ''
		selectedTrainers.value = []
		startDate.value = dayjs().format('YYYY-MM-DD')
		endDate.value = dayjs().add(3, 'month').format('YYYY-MM-DD')
		recentAssignments.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to assign course'))
	}
}
</script>
