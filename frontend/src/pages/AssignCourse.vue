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

		<div class="p-5">
			<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
				<!-- Assignment Form -->
				<div class="border rounded-lg p-6 bg-surface-white h-fit lg:col-span-1">
					<h2 class="text-lg font-semibold text-ink-gray-9 mb-5">
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
							class="w-full"
							:loading="assignResource.loading"
							:disabled="!selectedStudent || !selectedCourse"
							@click="assignCourse"
						>
							{{ __('Assign Course') }}
						</Button>
					</div>
				</div>

				<!-- All Assignments with Filters -->
				<div class="border rounded-lg overflow-hidden h-fit lg:col-span-2">
					<div class="px-6 py-4 bg-surface-gray-1 border-b">
						<h3 class="text-lg font-semibold text-ink-gray-9 mb-3">
							{{ __('Course Assignments') }}
						</h3>
						<!-- Filters -->
						<div class="flex flex-wrap gap-3">
							<div class="flex-1 min-w-[200px]">
								<Input
									v-model="searchQuery"
									type="text"
									:placeholder="__('Search student or course...')"
								>
									<template #prefix>
										<Search class="size-4 text-ink-gray-4" />
									</template>
								</Input>
							</div>
							<Autocomplete
								v-model="courseFilter"
								:options="courseFilterOptions"
								:placeholder="__('All Courses')"
								class="w-48"
							/>
							<Autocomplete
								v-model="trainerFilter"
								:options="trainerFilterOptions"
								:placeholder="__('All Trainers')"
								class="w-48"
							/>
							<Button
								v-if="searchQuery || courseFilter || trainerFilter"
								variant="ghost"
								@click="clearFilters"
							>
								{{ __('Clear Filters') }}
							</Button>
						</div>
					</div>

					<div
						v-if="allAssignments.loading"
						class="flex justify-center py-12"
					>
						<LoadingIndicator class="size-6" />
					</div>

					<div
						v-else-if="!filteredAssignments.length"
						class="text-center py-12 text-ink-gray-5"
					>
						{{ searchQuery || courseFilter || trainerFilter ? __('No assignments found matching filters') : __('No assignments yet') }}
					</div>

					<div v-else>
						<!-- Table View -->
						<table class="w-full">
							<thead>
								<tr class="border-b text-left text-sm text-ink-gray-5 bg-surface-gray-1">
									<th class="px-6 py-3">{{ __('Student') }}</th>
									<th class="px-6 py-3">{{ __('Course') }}</th>
									<th class="px-6 py-3">{{ __('Trainers') }}</th>
									<th class="px-6 py-3">{{ __('Dates') }}</th>
									<th class="px-6 py-3 text-center">{{ __('Action') }}</th>
								</tr>
							</thead>
							<tbody class="divide-y">
								<tr
									v-for="assignment in paginatedAssignments"
									:key="assignment.name"
									class="hover:bg-surface-gray-1 transition-colors"
								>
									<td class="px-6 py-4">
										<div class="font-medium text-ink-gray-9">
											{{ assignment.student_name }}
										</div>
										<div class="text-xs text-ink-gray-5">
											{{ assignment.member }}
										</div>
									</td>
									<td class="px-6 py-4">
										<div class="font-medium text-ink-gray-9">
											{{ assignment.course_title }}
										</div>
									</td>
									<td class="px-6 py-4">
										<div class="text-sm text-ink-gray-7">
											{{ assignment.trainers_names || __('Self-assigned') }}
										</div>
									</td>
									<td class="px-6 py-4">
										<div class="text-sm text-ink-gray-7">
											{{ dayjs(assignment.start_date).format('DD MMM YYYY') }}
										</div>
										<div class="text-xs text-ink-gray-5">
											{{ __('to') }} {{ dayjs(assignment.end_date).format('DD MMM YYYY') }}
										</div>
									</td>
									<td class="px-6 py-4 text-center">
										<div class="flex items-center justify-center gap-1">
											<Button
												variant="ghost"
												size="sm"
												@click="openEditTrainers(assignment)"
											>
												{{ __('Edit Trainers') }}
											</Button>
											<Button
												variant="ghost"
												size="sm"
												theme="red"
												:loading="unassignResource.loading"
												@click="unassignCourse(assignment)"
											>
												{{ __('Unassign') }}
											</Button>
										</div>
									</td>
								</tr>
							</tbody>
						</table>

						<!-- Pagination -->
						<div v-if="filteredAssignments.length > perPage" class="px-6 py-3 border-t bg-surface-gray-1 flex items-center justify-between">
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

						<!-- Summary -->
						<div class="px-6 py-3 bg-surface-gray-1 border-t text-sm text-ink-gray-5">
							{{ __('Showing {0} of {1} assignments', [paginatedAssignments.length, filteredAssignments.length]) }}
						</div>
					</div>
				</div>
			</div>
		</div>

		<Dialog
			v-model="showUnassignDialog"
			:options="{
				title: __('Unassign Course'),
				size: 'sm',
				actions: [
					{
						label: __('Cancel'),
						variant: 'ghost',
					},
					{
						label: __('Unassign'),
						variant: 'solid',
						theme: 'red',
						loading: unassignResource.loading,
						onClick: confirmUnassign,
					},
				],
			}"
		>
			<template #body-content>
				<div v-if="assignmentToUnassign">
					Are you sure you want to unassign
					<strong>{{ assignmentToUnassign.course_title }}</strong>
					from
					<strong>{{ assignmentToUnassign.student_name }}</strong>?
				</div>
			</template>
		</Dialog>

		<Dialog
			v-model="showEditTrainersDialog"
			:options="{
				title: __('Edit Trainers'),
				actions: [
					{
						label: __('Cancel'),
						variant: 'ghost',
					},
					{
						label: __('Save'),
						variant: 'solid',
						loading: updateTrainersResource.loading,
						onClick: confirmEditTrainers,
					},
				],
			}"
		>
			<template #body-content>
				<div v-if="assignmentToEdit" class="space-y-3">
					<p class="text-ink-gray-7">
						{{ __('Trainers for') }}
						<strong>{{ assignmentToEdit.course_title }}</strong>
						{{ __('assigned to') }}
						<strong>{{ assignmentToEdit.student_name }}</strong>
					</p>
					<Autocomplete
						v-model="editTrainers"
						:options="editTrainerOptions"
						:placeholder="__('Select one or more trainers...')"
						:multiple="true"
					/>
					<p class="text-xs text-ink-gray-5">
						{{
							__(
								'Adding a trainer to an already-scheduled feedback form sends it back for rescheduling. Removing a trainer who already gave feedback keeps their feedback.'
							)
						}}
					</p>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Button,
	Autocomplete,
	FormControl,
	Input,
	LoadingIndicator,
	createResource,
	Dialog,
	toast,
} from 'frappe-ui'
import { ref, computed, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import dayjs from 'dayjs'

const selectedStudent = ref('')
const selectedCourse = ref('')
const selectedTrainers = ref([])
const startDate = ref(dayjs().format('YYYY-MM-DD'))
const endDate = ref(dayjs().add(3, 'month').format('YYYY-MM-DD'))
const showUnassignDialog = ref(false)
const assignmentToUnassign = ref(null)
const showEditTrainersDialog = ref(false)
const assignmentToEdit = ref(null)
const editTrainers = ref([])
const searchQuery = ref('')
const courseFilter = ref('')
const trainerFilter = ref('')
const currentPage = ref(1)
const perPage = ref(25)

const perPageOptions = [
	{ label: '10', value: 10 },
	{ label: '25', value: 25 },
	{ label: '50', value: 50 },
	{ label: '100', value: 100 },
]

// Reset to page 1 when filters change
watch([searchQuery, courseFilter, trainerFilter], () => {
	currentPage.value = 1
})

// Reload course instructors when course selection changes
watch(selectedCourse, (newCourse) => {
	if (newCourse) {
		const courseValue = typeof newCourse === 'object' ? newCourse.value : newCourse
		courseInstructors.update({
			params: {
				course: courseValue,
			}
		})
		courseInstructors.reload()
		// Clear selected trainers when course changes
		selectedTrainers.value = []
	} else {
		// Reset instructors when course is cleared
		courseInstructors.data = null
		selectedTrainers.value = []
	}
})

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

const courseInstructors = createResource({
	url: 'lms.lms.api.get_course_instructors',
	params: {
		course: '',
	},
})

const allAssignments = createResource({
	url: 'lms.lms.custom.course_assignment.get_all_assignments',
	auto: true,
	onError(error) {
		console.error('Failed to load assignments:', error)
		toast.error(__('Failed to load assignments'))
	},
})

const studentOptions = computed(() => {
	if (!allUsers.data) return []
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

	// If a course is selected, filter trainers to only show course instructors
	if (selectedCourse.value && courseInstructors.data) {
		const instructorEmails = courseInstructors.data.map(i => i.instructor)
		return Object.values(allUsers.data)
			.filter((user) => instructorEmails.includes(user.name))
			.map((user) => ({
				label: user.full_name || user.name,
				value: user.name,
			}))
	}

	// If no course is selected, show all trainers
	return Object.values(allUsers.data)
		.filter((user) => user.is_trainer || user.is_master_trainer)
		.map((user) => ({
			label: user.full_name || user.name,
			value: user.name,
		}))
})

const courseFilterOptions = computed(() => {
	if (!allCourses.data) return []
	return [
		{ label: __('All Courses'), value: '' },
		...allCourses.data.map((course) => ({
			label: course.title || course.name,
			value: course.name,
		}))
	]
})

const trainerFilterOptions = computed(() => {
	if (!allUsers.data) return []
	const trainers = Object.values(allUsers.data)
		.filter((user) => user.is_trainer || user.is_master_trainer)
	return [
		{ label: __('All Trainers'), value: '' },
		...trainers.map((user) => ({
			label: user.full_name || user.name,
			value: user.name,
		}))
	]
})

const clearFilters = () => {
	searchQuery.value = ''
	courseFilter.value = ''
	trainerFilter.value = ''
}

const filteredAssignments = computed(() => {
	if (!allAssignments.data) return []

	let filtered = allAssignments.data

	// Search filter
	if (searchQuery.value) {
		const query = searchQuery.value.toLowerCase()
		filtered = filtered.filter(a =>
			a.student_name?.toLowerCase().includes(query) ||
			a.member?.toLowerCase().includes(query) ||
			a.course_title?.toLowerCase().includes(query)
		)
	}

	// Course filter - handle both string and object values from Autocomplete
	if (courseFilter.value) {
		const filterValue = typeof courseFilter.value === 'object' ? courseFilter.value.value : courseFilter.value
		filtered = filtered.filter(a => a.course === filterValue)
	}

	// Trainer filter - handle both string and object values from Autocomplete
	if (trainerFilter.value) {
		const filterValue = typeof trainerFilter.value === 'object' ? trainerFilter.value.value : trainerFilter.value
		filtered = filtered.filter(a =>
			a.trainers?.includes(filterValue)
		)
	}

	return filtered
})

const paginatedAssignments = computed(() => {
	const start = (currentPage.value - 1) * perPage.value
	const end = start + perPage.value
	return filteredAssignments.value.slice(start, end)
})

const totalPages = computed(() => {
	return Math.ceil(filteredAssignments.value.length / perPage.value) || 1
})

const assignResource = createResource({
	url: 'lms.lms.custom.course_assignment.assign_course_to_student',
})

const unassignResource = createResource({
	url: 'lms.lms.custom.course_assignment.unassign_course_from_student',
})

const updateTrainersResource = createResource({
	url: 'lms.lms.custom.course_assignment.update_assignment_trainers',
})

// Instructors of the assignment's course — loaded when the Edit Trainers dialog opens.
const editCourseInstructors = createResource({
	url: 'lms.lms.api.get_course_instructors',
})

// Only trainers that belong to the course (its instructors) or are already assigned to
// this assignment may be chosen.
const editTrainerOptions = computed(() => {
	if (!allUsers.data) return []
	const emails = new Set()
	;(editCourseInstructors.data || []).forEach((i) => emails.add(i.instructor))
	;(assignmentToEdit.value?.trainers || []).forEach((t) => emails.add(t))
	return [...emails].map((email) => ({
		label: allUsers.data[email]?.full_name || email,
		value: email,
	}))
})

const openEditTrainers = (assignment) => {
	assignmentToEdit.value = assignment
	editTrainers.value = (assignment.trainers || []).map((email) => ({
		label: (allUsers.data && allUsers.data[email]?.full_name) || email,
		value: email,
	}))
	editCourseInstructors.submit({ course: assignment.course })
	showEditTrainersDialog.value = true
}

const confirmEditTrainers = () => {
	if (!assignmentToEdit.value) return
	updateTrainersResource.submit(
		{
			batch: assignmentToEdit.value.batch,
			trainers: (editTrainers.value || []).map((t) => t.value),
		},
		{
			onSuccess(data) {
				let msg = data?.message || __('Trainers updated')
				if (data?.unscheduled) {
					msg += '. ' + __('Feedback sessions need rescheduling.')
				}
				toast.success(msg)
				showEditTrainersDialog.value = false
				assignmentToEdit.value = null
				allAssignments.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || __('Failed to update trainers'))
			},
		}
	)
}

const unassignCourse = (assignment) => {
	assignmentToUnassign.value = assignment
	showUnassignDialog.value = true
}

const confirmUnassign = async () => {
	try {
		await unassignResource.submit({
			student_email: assignmentToUnassign.value.member,
			course: assignmentToUnassign.value.course,
		})
		toast.success(unassignResource.data?.message || __('Course unassigned successfully'))
		showUnassignDialog.value = false
		assignmentToUnassign.value = null
		allAssignments.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to unassign course'))
	}
}

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
		allAssignments.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to assign course'))
	}
}
</script>
