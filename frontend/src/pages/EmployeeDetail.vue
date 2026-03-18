<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Employees'), route: { name: 'EmployeeManagement' } },
					{ label: employeeData.data?.employee_name || __('Employee') },
				]"
			/>
			<div class="flex items-center gap-2" v-if="employeeData.data">
				<Button
					variant="subtle"
					size="sm"
					@click="openEditModal"
				>
					<template #prefix>
						<Pencil class="size-3.5" />
					</template>
					{{ __('Edit') }}
				</Button>
				<Button
					v-if="employeeData.data.status === 'Active'"
					variant="subtle"
					theme="red"
					size="sm"
					@click="confirmDeactivate"
				>
					{{ __('Deactivate') }}
				</Button>
				<Button
					v-else
					variant="subtle"
					theme="green"
					size="sm"
					@click="handleReactivate"
				>
					{{ __('Reactivate') }}
				</Button>
			</div>
		</header>

		<!-- Loading State -->
		<div
			v-if="employeeData.loading"
			class="flex items-center justify-center py-20"
		>
			<LoadingIndicator class="size-8" />
		</div>

		<div v-else-if="employeeData.data" class="p-5">
			<!-- Deactivated Banner -->
			<div
				v-if="employeeData.data.status !== 'Active'"
				class="mb-4 p-3 bg-surface-red-1 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2"
			>
				<span class="font-medium">{{ __('This employee is deactivated.') }}</span>
			</div>

			<!-- Employee Header -->
			<div class="flex items-start space-x-4 mb-6">
				<UserAvatar
					:user="{
						name: employeeData.data.user_id,
						full_name: employeeData.data.employee_name,
						user_image: employeeData.data.image,
					}"
					size="2xl"
				/>
				<div>
					<h1 class="text-xl font-bold text-ink-gray-9">
						{{ employeeData.data.employee_name }}
					</h1>
					<p class="text-ink-gray-5 mt-0.5">
						{{ employeeData.data.designation || '' }}
						{{ employeeData.data.department ? ' · ' + employeeData.data.department : '' }}
					</p>
					<p
						v-if="employeeData.data.user_id"
						class="text-sm text-ink-gray-5 mt-0.5"
					>
						{{ employeeData.data.user_id }}
					</p>
					<div class="flex items-center gap-2 mt-2 flex-wrap">
						<Badge
							v-for="role in employeeData.data.lms_roles"
							:key="role"
							:label="role"
							variant="subtle"
							theme="blue"
						/>
						<Badge
							v-if="employeeData.data.role_profile"
							:label="employeeData.data.role_profile"
							variant="subtle"
							theme="green"
						/>
						<button
							v-if="employeeData.data.role_profile && employeeData.data.user_id"
							class="text-xs text-red-500 hover:text-red-700 underline"
							@click="confirmUnassignRole"
						>
							{{ __('Unassign Role') }}
						</button>
					</div>
				</div>
			</div>

			<!-- Info Cards -->
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
				<div class="border rounded-lg p-4">
					<div class="flex items-center justify-between">
						<div class="text-sm text-ink-gray-5">{{ __('Manager') }}</div>
						<Button
							variant="ghost"
							size="sm"
							@click="openManagerModal"
						>
							<Pencil class="size-3.5" />
						</Button>
					</div>
					<div class="text-ink-gray-9 font-medium mt-1">
						{{ employeeData.data.manager_name || __('None') }}
					</div>
				</div>
				<div class="border rounded-lg p-4">
					<div class="text-sm text-ink-gray-5">{{ __('Company') }}</div>
					<div class="text-ink-gray-9 font-medium mt-1">
						{{ employeeData.data.company || '-' }}
					</div>
				</div>
				<div class="border rounded-lg p-4">
					<div class="text-sm text-ink-gray-5">{{ __('Date of Joining') }}</div>
					<div class="text-ink-gray-9 font-medium mt-1">
						{{
							employeeData.data.date_of_joining
								? dayjs(employeeData.data.date_of_joining).format('DD MMM YYYY')
								: '-'
						}}
					</div>
				</div>
			</div>

			<!-- Tabs -->
			<TabButtons v-model="currentTab" :buttons="tabs" class="mb-4" />

			<!-- Course Enrollments Tab -->
			<div v-if="currentTab === 'enrollments'">
				<div
					v-if="!employeeData.data.enrollments?.length"
					class="text-center py-10 border rounded-lg text-ink-gray-5"
				>
					{{ __('No course enrollments') }}
				</div>

				<div v-else class="border rounded-lg divide-y">
					<div
						v-for="enrollment in employeeData.data.enrollments"
						:key="enrollment.name"
						class="px-4 py-3 flex items-center justify-between"
					>
						<div>
							<div class="font-medium text-ink-gray-9">
								{{ enrollment.course_title }}
							</div>
							<div class="text-sm text-ink-gray-5">
								{{ __('Enrolled') }}
								{{ dayjs(enrollment.creation).format('DD MMM YYYY') }}
							</div>
						</div>
						<div class="flex items-center space-x-3">
							<div class="flex items-center space-x-2">
								<div class="w-24 bg-surface-gray-2 rounded-full h-2">
									<div
										class="bg-blue-500 h-2 rounded-full transition-all"
										:style="{ width: (enrollment.progress || 0) + '%' }"
									></div>
								</div>
								<span class="text-sm text-ink-gray-7">
									{{ enrollment.progress || 0 }}%
								</span>
							</div>
							<Badge
								:label="enrollment.status"
								variant="subtle"
								:theme="getStatusTheme(enrollment.status)"
							/>
							<Button
								variant="subtle"
								theme="red"
								size="sm"
								@click.stop="confirmUnassignCourse(enrollment)"
							>
								{{ __('Unassign') }}
							</Button>
							<Button
								v-if="userResource.data?.is_system_manager || userResource.data?.lms_roles?.includes('LMS Master Trainer') || userResource.data?.lms_roles?.includes('LMS HR')"
								variant="subtle"
								theme="blue"
								size="sm"
								@click.stop="openUnlockChapterModal(enrollment)"
							>
								{{ __('Unlock Chapter') }}
							</Button>
						</div>
					</div>
				</div>

				<!-- Assign Course Button -->
				<div class="mt-4">
					<Button
						variant="solid"
						@click="
							$router.push({
								name: 'AssignCourse',
							})
						"
					>
						{{ __('Assign New Course') }}
					</Button>
				</div>
			</div>

			<!-- Quiz Submissions Tab -->
			<div v-if="currentTab === 'quizzes'">
				<div
					v-if="!employeeData.data.quiz_submissions?.length"
					class="text-center py-10 border rounded-lg text-ink-gray-5"
				>
					{{ __('No quiz submissions') }}
				</div>

				<div v-else class="border rounded-lg divide-y">
					<div
						v-for="quiz in employeeData.data.quiz_submissions"
						:key="quiz.name"
						class="px-4 py-3 flex items-center justify-between"
					>
						<div>
							<div class="font-medium text-ink-gray-9">
								{{ quiz.quiz }}
							</div>
							<div class="text-sm text-ink-gray-5">
								{{ dayjs(quiz.creation).format('DD MMM YYYY') }}
							</div>
						</div>
						<Badge
							:label="__('Score') + ': ' + (quiz.score || 0)"
							variant="subtle"
							theme="blue"
						/>
					</div>
				</div>
			</div>

			<!-- Certificates Tab -->
			<div v-if="currentTab === 'certificates'">
				<div
					v-if="!employeeData.data.certificates?.length"
					class="text-center py-10 border rounded-lg text-ink-gray-5"
				>
					{{ __('No certificates earned') }}
				</div>

				<div v-else class="border rounded-lg divide-y">
					<div
						v-for="cert in employeeData.data.certificates"
						:key="cert.name"
						class="px-4 py-3 flex items-center justify-between"
					>
						<div>
							<div class="font-medium text-ink-gray-9">
								{{ cert.course }}
							</div>
							<div class="text-sm text-ink-gray-5">
								{{ __('Issued') }}
								{{ dayjs(cert.creation).format('DD MMM YYYY') }}
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Change Manager Modal -->
		<Dialog
			v-model="showManagerModal"
			:options="{ title: __('Change Manager') }"
		>
			<template #body-content>
				<div class="space-y-4">
					<p class="text-ink-gray-7">
						{{ __('Select a manager for') }}
						<strong>{{ employeeData.data?.employee_name }}</strong>
					</p>
					<Autocomplete
						v-model="selectedManager"
						:options="managerOptions"
						:placeholder="__('Search for a manager...')"
					/>
				</div>
			</template>
			<template #actions>
				<div class="flex space-x-2">
					<Button
						v-if="employeeData.data?.reports_to"
						variant="subtle"
						theme="red"
						:loading="updateManager.loading"
						@click="removeManager"
					>
						{{ __('Remove Manager') }}
					</Button>
					<Button
						variant="solid"
						:loading="updateManager.loading"
						:disabled="!selectedManager"
						@click="saveManager"
					>
						{{ __('Save') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Edit Employee Modal -->
		<Dialog
			v-model="showEditModal"
			:options="{ title: __('Edit Employee'), size: 'lg' }"
		>
			<template #body-content>
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Employee Name') }} *
						</label>
						<FormControl
							v-model="editEmployee.employee_name"
							type="text"
							:placeholder="__('Full name')"
						/>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Gender') }}
							</label>
							<Autocomplete
								v-model="editEmployee.gender"
								:options="genderOptions"
								:placeholder="__('Select gender')"
							/>
						</div>
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Date of Birth') }}
							</label>
							<FormControl
								v-model="editEmployee.date_of_birth"
								type="date"
							/>
						</div>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Date of Joining') }}
							</label>
							<FormControl
								v-model="editEmployee.date_of_joining"
								type="date"
							/>
						</div>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Department') }}
							</label>
							<Autocomplete
								v-if="filterOptions"
								v-model="editEmployee.department"
								:options="editDepartmentOptions"
								:placeholder="__('Department')"
							/>
						</div>
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Designation') }}
							</label>
							<Autocomplete
								v-if="filterOptions"
								v-model="editEmployee.designation"
								:options="editDesignationOptions"
								:placeholder="__('Designation')"
							/>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<Button
					variant="solid"
					:loading="saveEmployeeEdit.loading"
					:disabled="!editEmployee.employee_name"
					@click="submitEditEmployee"
				>
					{{ __('Save Changes') }}
				</Button>
			</template>
		</Dialog>

		<!-- Confirm Deactivate Modal -->
		<Dialog
			v-model="showDeactivateModal"
			:options="{ title: __('Deactivate Employee') }"
		>
			<template #body-content>
				<div class="space-y-4">
					<p class="text-ink-gray-7">
						{{ __('Select deactivation type for') }}
						<strong>{{ employeeData.data?.employee_name }}</strong>:
					</p>
					<div class="space-y-2">
						<label
							class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer"
							:class="deactivateStatus === 'Inactive' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'"
						>
							<input
								type="radio"
								v-model="deactivateStatus"
								value="Inactive"
								class="mt-0.5"
							/>
							<div>
								<div class="font-medium text-ink-gray-9">{{ __('Inactive') }}</div>
								<div class="text-sm text-ink-gray-5">
									{{ __('Temporarily deactivate. Employee can be reactivated later.') }}
								</div>
							</div>
						</label>
						<label
							class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer"
							:class="deactivateStatus === 'Left' ? 'border-red-500 bg-red-50' : 'border-gray-200'"
						>
							<input
								type="radio"
								v-model="deactivateStatus"
								value="Left"
								class="mt-0.5"
							/>
							<div>
								<div class="font-medium text-ink-gray-9">{{ __('Left') }}</div>
								<div class="text-sm text-ink-gray-5">
									{{ __('Employee has left the organization. Requires a relieving date.') }}
								</div>
							</div>
						</label>
					</div>
					<div v-if="deactivateStatus === 'Left'">
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Relieving Date') }} *
						</label>
						<FormControl v-model="relievingDate" type="date" />
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex space-x-2">
					<Button variant="subtle" @click="showDeactivateModal = false">
						{{ __('Cancel') }}
					</Button>
					<Button
						variant="solid"
						theme="red"
						:loading="doDeactivate.loading"
						:disabled="deactivateStatus === 'Left' && !relievingDate"
						@click="handleDeactivate"
					>
						{{ __('Confirm') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Confirm Unassign Course Modal -->
		<Dialog
			v-model="showUnassignCourseModal"
			:options="{ title: __('Unassign Course') }"
		>
			<template #body-content>
				<div class="space-y-3">
					<p class="text-ink-gray-7">
						{{ __('Remove enrollment for') }}
						<strong>{{ selectedEnrollment?.course_title }}</strong>
						{{ __('from') }}
						<strong>{{ employeeData.data?.employee_name }}</strong>?
					</p>
					<p class="text-sm text-ink-gray-5">
						{{ __('This will permanently delete their progress for this course.') }}
					</p>
				</div>
			</template>
			<template #actions>
				<div class="flex space-x-2">
					<Button variant="subtle" @click="showUnassignCourseModal = false">
						{{ __('Cancel') }}
					</Button>
					<Button
						variant="solid"
						theme="red"
						:loading="doUnassignCourse.loading"
						@click="handleUnassignCourse"
					>
						{{ __('Unassign') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Confirm Unassign Role Modal -->
		<Dialog
			v-model="showUnassignRoleModal"
			:options="{ title: __('Unassign Role') }"
		>
			<template #body-content>
				<div class="space-y-3">
					<p class="text-ink-gray-7">
						{{ __('Remove role profile') }}
						<strong>{{ employeeData.data?.role_profile }}</strong>
						{{ __('from') }}
						<strong>{{ employeeData.data?.employee_name }}</strong>?
					</p>
				</div>
			</template>
			<template #actions>
				<div class="flex space-x-2">
					<Button variant="subtle" @click="showUnassignRoleModal = false">
						{{ __('Cancel') }}
					</Button>
					<Button
						variant="solid"
						theme="red"
						:loading="doUnassignRole.loading"
						@click="handleUnassignRole"
					>
						{{ __('Unassign') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Unlock Chapter Modal -->
		<Dialog
			v-model="showUnlockChapterModal"
			:options="{ title: __('Unlock Chapter') }"
		>
			<template #body-content>
				<div class="space-y-4">
					<p class="text-ink-gray-7">
						{{ __('Select a chapter to unlock for') }}
						<strong>{{ employeeData.data?.employee_name }}</strong>
						{{ __('in course') }}
						<strong>{{ selectedCourseForUnlock?.course_title }}</strong>
					</p>
					<div v-if="lockedChapters.loading" class="text-ink-gray-5">
						{{ __('Loading locked chapters...') }}
					</div>
					<div v-else-if="!lockedChapters.data?.length" class="text-ink-gray-5">
						{{ __('No locked chapters available to unlock') }}
					</div>
					<div v-else class="space-y-2">
						<label class="text-sm font-medium text-ink-gray-7">
							{{ __('Select Chapter') }}
						</label>
						<select
							v-model="selectedChapterToUnlock"
							class="form-control"
						>
							<option value="">{{ __('-- Select Chapter --') }}</option>
							<option
								v-for="chapter in lockedChapters.data"
								:key="chapter.name"
								:value="chapter.name"
							>
								{{ chapter.idx }}. {{ chapter.title }}
							</option>
						</select>
					</div>
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
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Badge,
	Button,
	TabButtons,
	LoadingIndicator,
	Autocomplete,
	Dialog,
	FormControl,
	createResource,
	toast,
} from 'frappe-ui'
import { Pencil } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import dayjs from 'dayjs'
import { ref, computed, reactive } from 'vue'

const props = defineProps({
	employeeId: {
		type: String,
		required: true,
	},
})

const currentTab = ref('enrollments')

const tabs = [
	{ label: __('Enrollments'), value: 'enrollments' },
	{ label: __('Quizzes'), value: 'quizzes' },
	{ label: __('Certificates'), value: 'certificates' },
]

const employeeData = createResource({
	url: 'lms.lms.custom.dashboard_api.get_employee_detail',
	params: {
		employee: props.employeeId,
	},
	auto: true,
})

const getStatusTheme = (status) => {
	const themes = {
		Completed: 'green',
		'In Progress': 'blue',
		'Not Started': 'gray',
	}
	return themes[status] || 'gray'
}

// Manager modal
const showManagerModal = ref(false)
const selectedManager = ref('')

const allEmployees = createResource({
	url: 'lms.lms.custom.dashboard_api.get_employee_options',
})

const managerOptions = computed(() => {
	if (!allEmployees.data) return []
	return allEmployees.data
		.filter((emp) => emp.name !== props.employeeId)
		.map((emp) => ({
			label: `${emp.employee_name} (${emp.name})`,
			value: emp.name,
		}))
})

const openManagerModal = () => {
	selectedManager.value = ''
	allEmployees.fetch()
	showManagerModal.value = true
}

const updateManager = createResource({
	url: 'lms.lms.custom.dashboard_api.update_employee_manager',
})

const saveManager = async () => {
	if (!selectedManager.value) return
	try {
		await updateManager.submit({
			employee: props.employeeId,
			reports_to: selectedManager.value.value,
		})
		toast.success(updateManager.data?.message || __('Manager updated'))
		showManagerModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to update manager'))
	}
}

const removeManager = async () => {
	try {
		await updateManager.submit({
			employee: props.employeeId,
			reports_to: '',
		})
		toast.success(__('Manager removed'))
		showManagerModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to remove manager'))
	}
}

// ─── Edit Employee ───────────────────────────────────────────────────────────
const showEditModal = ref(false)
const editEmployee = reactive({
	employee_name: '',
	gender: '',
	date_of_birth: '',
	date_of_joining: '',
	department: '',
	designation: '',
})

const genderOptions = [
	{ label: __('Male'), value: 'Male' },
	{ label: __('Female'), value: 'Female' },
	{ label: __('Other'), value: 'Other' },
]

const filterOptions = createResource({
	url: 'lms.lms.custom.dashboard_api.get_hr_filters',
	auto: true,
})

const editDepartmentOptions = computed(() => {
	if (!filterOptions.data?.departments) return []
	return [
		{ label: __('— None —'), value: '' },
		...filterOptions.data.departments.map((d) => ({ label: d, value: d })),
	]
})

const editDesignationOptions = computed(() => {
	if (!filterOptions.data?.designations) return []
	return [
		{ label: __('— None —'), value: '' },
		...filterOptions.data.designations.map((d) => ({ label: d, value: d })),
	]
})

const openEditModal = () => {
	const d = employeeData.data
	editEmployee.employee_name = d.employee_name || ''
	editEmployee.gender = d.gender
		? { label: d.gender, value: d.gender }
		: ''
	editEmployee.date_of_birth = d.date_of_birth || ''
	editEmployee.date_of_joining = d.date_of_joining || ''
	editEmployee.department = d.department
		? { label: d.department, value: d.department }
		: ''
	editEmployee.designation = d.designation
		? { label: d.designation, value: d.designation }
		: ''
	showEditModal.value = true
}

const saveEmployeeEdit = createResource({
	url: 'lms.lms.custom.dashboard_api.update_employee',
})

const submitEditEmployee = async () => {
	if (!editEmployee.employee_name) return
	try {
		await saveEmployeeEdit.submit({
			employee: props.employeeId,
			employee_name: editEmployee.employee_name,
			gender: editEmployee.gender?.value || editEmployee.gender || '',
			date_of_birth: editEmployee.date_of_birth || '',
			date_of_joining: editEmployee.date_of_joining || '',
			department: editEmployee.department?.value ?? editEmployee.department ?? '',
			designation: editEmployee.designation?.value ?? editEmployee.designation ?? '',
		})
		toast.success(saveEmployeeEdit.data?.message || __('Employee updated'))
		showEditModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to update employee'))
	}
}

// ─── Deactivate Employee ─────────────────────────────────────────────────────
const showDeactivateModal = ref(false)
const deactivateStatus = ref('Inactive')
const relievingDate = ref('')

const confirmDeactivate = () => {
	deactivateStatus.value = 'Inactive'
	relievingDate.value = ''
	showDeactivateModal.value = true
}

const doDeactivate = createResource({
	url: 'lms.lms.custom.dashboard_api.deactivate_employee',
})

const handleDeactivate = async () => {
	try {
		await doDeactivate.submit({
			employee: props.employeeId,
			status: deactivateStatus.value,
			relieving_date: deactivateStatus.value === 'Left' ? relievingDate.value : '',
		})
		toast.success(doDeactivate.data?.message || __('Employee deactivated'))
		showDeactivateModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to deactivate employee'))
	}
}

const doReactivate = createResource({
	url: 'lms.lms.custom.dashboard_api.reactivate_employee',
})

const handleReactivate = async () => {
	try {
		await doReactivate.submit({ employee: props.employeeId })
		toast.success(doReactivate.data?.message || __('Employee reactivated'))
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to reactivate employee'))
	}
}

// ─── Unassign Course ─────────────────────────────────────────────────────────
const showUnassignCourseModal = ref(false)
const selectedEnrollment = ref(null)

const confirmUnassignCourse = (enrollment) => {
	selectedEnrollment.value = enrollment
	showUnassignCourseModal.value = true
}

const doUnassignCourse = createResource({
	url: 'lms.lms.custom.dashboard_api.unassign_employee_course',
})

const handleUnassignCourse = async () => {
	try {
		await doUnassignCourse.submit({
			enrollment: selectedEnrollment.value.name,
		})
		toast.success(__('Course unassigned successfully'))
		showUnassignCourseModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to unassign course'))
	}
}

// ─── Unassign Role ────────────────────────────────────────────────────────────
const showUnassignRoleModal = ref(false)

const confirmUnassignRole = () => {
	showUnassignRoleModal.value = true
}

const doUnassignRole = createResource({
	url: 'lms.lms.custom.dashboard_api.unassign_employee_role',
})

const handleUnassignRole = async () => {
	try {
		await doUnassignRole.submit({ employee: props.employeeId })
		toast.success(doUnassignRole.data?.message || __('Role unassigned'))
		showUnassignRoleModal.value = false
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to unassign role'))
	}
}

// ─── Unlock Chapter ──────────────────────────────────────────────────────────
const showUnlockChapterModal = ref(false)
const selectedCourseForUnlock = ref(null)
const selectedChapterToUnlock = ref('')

const lockedChapters = createResource({
	url: 'lms.lms.custom.dashboard_api.get_locked_chapters_for_employee',
	makeParams(values) {
		return {
			employee: props.employeeId,
			course: values.course,
		}
	},
})

const doUnlockChapter = createResource({
	url: 'lms.lms.custom.dashboard_api.unlock_chapter_for_employee',
})

const openUnlockChapterModal = (enrollment) => {
	selectedCourseForUnlock.value = enrollment
	selectedChapterToUnlock.value = ''
	showUnlockChapterModal.value = true

	// Fetch locked chapters for this course
	lockedChapters.submit({
		course: enrollment.course,
	})
}

const handleUnlockChapter = async () => {
	if (!selectedChapterToUnlock.value) {
		toast.error(__('Please select a chapter to unlock'))
		return
	}

	try {
		await doUnlockChapter.submit({
			employee: props.employeeId,
			course: selectedCourseForUnlock.value.course,
			chapter: selectedChapterToUnlock.value,
		})
		toast.success(
			doUnlockChapter.data?.message || __('Chapter unlocked successfully')
		)
		showUnlockChapterModal.value = false
		selectedChapterToUnlock.value = ''
		employeeData.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to unlock chapter'))
	}
}
</script>
