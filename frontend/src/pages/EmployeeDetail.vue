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
		</header>

		<!-- Loading State -->
		<div
			v-if="employeeData.loading"
			class="flex items-center justify-center py-20"
		>
			<LoadingIndicator class="size-8" />
		</div>

		<div v-else-if="employeeData.data" class="p-5">
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
					<div class="flex items-center gap-2 mt-2">
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
	createResource,
	toast,
} from 'frappe-ui'
import { Pencil } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import dayjs from 'dayjs'
import { ref, computed } from 'vue'

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
</script>
