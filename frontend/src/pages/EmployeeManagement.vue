<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Employees') },
				]"
			/>
			<Button variant="solid" @click="openAddModal">
				<template #prefix>
					<Plus class="size-4" />
				</template>
				{{ __('Add Employee') }}
			</Button>
		</header>

		<div class="p-5">
			<!-- Filters -->
			<div class="flex flex-wrap items-center gap-3 mb-4">
				<div class="flex-1 min-w-[200px] max-w-md">
					<FormControl
						v-model="searchQuery"
						type="text"
						:placeholder="__('Search by name or email...')"
						@input="debouncedSearch"
					>
						<template #prefix>
							<Search class="size-4 text-ink-gray-4" />
						</template>
					</FormControl>
				</div>

				<Autocomplete
					v-if="filters.data"
					v-model="selectedDepartment"
					:options="departmentOptions"
					:placeholder="__('Department')"
					@update:modelValue="loadEmployees"
				/>

				<Autocomplete
					v-if="filters.data"
					v-model="selectedDesignation"
					:options="designationOptions"
					:placeholder="__('Designation')"
					@update:modelValue="loadEmployees"
				/>
			</div>

			<!-- Loading State -->
			<div
				v-if="employees.loading"
				class="flex items-center justify-center py-20"
			>
				<LoadingIndicator class="size-8" />
			</div>

			<!-- Empty State -->
			<div
				v-else-if="!employees.data?.employees?.length"
				class="text-center py-20"
			>
				<UsersIcon class="size-12 mx-auto text-ink-gray-4 stroke-1" />
				<p class="mt-3 text-ink-gray-5">
					{{ __('No employees found') }}
				</p>
			</div>

			<!-- Employee Table -->
			<div v-else class="border rounded-lg overflow-hidden">
				<table class="w-full">
					<thead>
						<tr class="border-b text-left text-sm text-ink-gray-5 bg-surface-gray-1">
							<th class="px-4 py-3">{{ __('Employee') }}</th>
							<th class="px-4 py-3">{{ __('Department') }}</th>
							<th class="px-4 py-3">{{ __('Designation') }}</th>
							<th class="px-4 py-3">{{ __('Manager') }}</th>
							<th class="px-4 py-3">{{ __('LMS Roles') }}</th>
							<th class="px-4 py-3">{{ __('Courses') }}</th>
							<th class="px-4 py-3">{{ __('Progress') }}</th>
							<th class="px-4 py-3">{{ __('Actions') }}</th>
						</tr>
					</thead>
					<tbody class="divide-y">
						<tr
							v-for="emp in employees.data.employees"
							:key="emp.name"
							class="hover:bg-surface-gray-1 cursor-pointer"
							@click="
								$router.push({
									name: 'EmployeeDetail',
									params: { employeeId: emp.name },
								})
							"
						>
							<td class="px-4 py-3">
								<div class="flex items-center space-x-3">
									<UserAvatar
										:user="{
											name: emp.user_id,
											full_name: emp.employee_name,
											user_image: emp.image,
										}"
										size="md"
									/>
									<div>
										<div class="font-medium text-ink-gray-9">
											{{ emp.employee_name }}
										</div>
										<div class="text-xs text-ink-gray-5">
											{{ emp.user_id || __('No user linked') }}
										</div>
									</div>
								</div>
							</td>
							<td class="px-4 py-3 text-ink-gray-7">
								{{ emp.department || '-' }}
							</td>
							<td class="px-4 py-3 text-ink-gray-7">
								{{ emp.designation || '-' }}
							</td>
							<td class="px-4 py-3 text-ink-gray-7">
								{{ emp.manager_name || '-' }}
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-wrap gap-1">
									<Badge
										v-for="role in emp.lms_roles"
										:key="role"
										:label="role"
										variant="subtle"
										theme="blue"
										size="sm"
									/>
									<span
										v-if="!emp.lms_roles?.length"
										class="text-ink-gray-5 text-sm"
									>
										-
									</span>
								</div>
							</td>
							<td class="px-4 py-3 text-ink-gray-7">
								{{ emp.total_courses }}
							</td>
							<td class="px-4 py-3">
								<div class="flex items-center space-x-2">
									<div class="w-20 bg-surface-gray-2 rounded-full h-2">
										<div
											class="bg-blue-500 h-2 rounded-full transition-all"
											:style="{ width: emp.avg_progress + '%' }"
										></div>
									</div>
									<span class="text-sm text-ink-gray-7">
										{{ emp.avg_progress }}%
									</span>
								</div>
							</td>
							<td class="px-4 py-3">
								<Button
									variant="subtle"
									size="sm"
									@click.stop="openRoleModal(emp)"
								>
									{{ __('Assign Role') }}
								</Button>
							</td>
						</tr>
					</tbody>
				</table>

				<!-- Pagination -->
				<div
					v-if="employees.data.total_count > pageSize"
					class="flex items-center justify-between px-4 py-3 border-t bg-surface-gray-1"
				>
					<span class="text-sm text-ink-gray-5">
						{{ __('Showing') }}
						{{ currentStart + 1 }}-{{
							Math.min(
								currentStart + pageSize,
								employees.data.total_count
							)
						}}
						{{ __('of') }} {{ employees.data.total_count }}
					</span>
					<div class="flex space-x-2">
						<Button
							variant="subtle"
							size="sm"
							:disabled="currentStart === 0"
							@click="prevPage"
						>
							{{ __('Previous') }}
						</Button>
						<Button
							variant="subtle"
							size="sm"
							:disabled="
								currentStart + pageSize >=
								employees.data.total_count
							"
							@click="nextPage"
						>
							{{ __('Next') }}
						</Button>
					</div>
				</div>
			</div>
		</div>

		<!-- Add Employee Modal -->
		<Dialog
			v-model="showAddModal"
			:options="{ title: __('Add New Employee'), size: 'lg' }"
		>
			<template #body-content>
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Employee Name') }} *
						</label>
						<FormControl
							v-model="newEmployee.employee_name"
							type="text"
							:placeholder="__('Full name')"
						/>
					</div>
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Email') }}
						</label>
						<FormControl
							v-model="newEmployee.user_email"
							type="email"
							:placeholder="__('employee@company.com')"
						/>
						<label
							v-if="newEmployee.user_email"
							class="flex items-center gap-2 mt-2 text-sm text-ink-gray-7 cursor-pointer"
						>
							<input
								type="checkbox"
								v-model="newEmployee.create_user"
								class="rounded border-gray-300"
							/>
							{{ __('Create user account (if email does not already exist)') }}
						</label>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Gender') }} *
							</label>
							<Autocomplete
								v-model="newEmployee.gender"
								:options="genderOptions"
								:placeholder="__('Select gender')"
							/>
						</div>
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Date of Birth') }} *
							</label>
							<FormControl
								v-model="newEmployee.date_of_birth"
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
								v-if="filters.data"
								v-model="newEmployee.department"
								:options="departmentOptions"
								:placeholder="__('Department')"
							/>
						</div>
						<div>
							<label class="block text-sm font-medium text-ink-gray-7 mb-1">
								{{ __('Designation') }}
							</label>
							<Autocomplete
								v-if="filters.data"
								v-model="newEmployee.designation"
								:options="designationOptions"
								:placeholder="__('Designation')"
							/>
						</div>
					</div>
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Manager (Reports To)') }}
						</label>
						<Autocomplete
							v-model="newEmployee.reports_to"
							:options="managerOptions"
							:placeholder="__('Select manager...')"
						/>
					</div>
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Role Profile') }}
						</label>
						<Autocomplete
							v-model="newEmployee.role_profile"
							:options="roleProfileOptions"
							:placeholder="__('Select role profile...')"
						/>
					</div>
				</div>
			</template>
			<template #actions>
				<Button
					variant="solid"
					:loading="createEmployee.loading"
					:disabled="!newEmployee.employee_name || !newEmployee.gender || !newEmployee.date_of_birth"
					@click="addEmployee"
				>
					{{ __('Create Employee') }}
				</Button>
			</template>
		</Dialog>

		<!-- Role Assignment Modal -->
		<Dialog
			v-model="showRoleModal"
			:options="{ title: __('Assign Role Profile') }"
		>
			<template #body-content>
				<div class="space-y-4">
					<p class="text-ink-gray-7">
						{{ __('Assign a role profile to') }}
						<strong>{{ selectedEmployee?.employee_name }}</strong>
					</p>

					<div v-if="!selectedEmployee?.user_id" class="p-3 bg-surface-amber-2 rounded-md text-sm">
						{{ __('This employee has no linked User account. Please link a User account first.') }}
					</div>

					<div v-else>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Role Profile') }}
						</label>
						<Autocomplete
							v-model="selectedRoleProfile"
							:options="roleProfileOptions"
							:placeholder="__('Select a role profile...')"
						/>
					</div>
				</div>
			</template>
			<template #actions>
				<Button
					v-if="selectedEmployee?.user_id"
					variant="solid"
					:loading="saveRole.loading"
					:disabled="!selectedRoleProfile"
					@click="assignRole"
				>
					{{ __('Save') }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Button,
	FormControl,
	Autocomplete,
	Badge,
	LoadingIndicator,
	Dialog,
	createResource,
	toast,
} from 'frappe-ui'
import { Search, Users as UsersIcon, Plus } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'
import { ref, computed, reactive } from 'vue'

const searchQuery = ref('')
const selectedDepartment = ref('')
const selectedDesignation = ref('')
const currentStart = ref(0)
const pageSize = 20
const showRoleModal = ref(false)
const selectedEmployee = ref(null)
const selectedRoleProfile = ref('')

let searchTimeout = null
const debouncedSearch = () => {
	clearTimeout(searchTimeout)
	searchTimeout = setTimeout(() => {
		currentStart.value = 0
		loadEmployees()
	}, 300)
}

const filters = createResource({
	url: 'lms.lms.custom.dashboard_api.get_hr_filters',
	auto: true,
})

const employees = createResource({
	url: 'lms.lms.custom.dashboard_api.get_hr_employees',
	params: {
		search: '',
		department: '',
		designation: '',
		start: 0,
		limit: pageSize,
	},
	auto: true,
})

const loadEmployees = () => {
	employees.submit({
		search: searchQuery.value,
		department: selectedDepartment.value?.value || '',
		designation: selectedDesignation.value?.value || '',
		start: currentStart.value,
		limit: pageSize,
	})
}

const departmentOptions = computed(() => {
	if (!filters.data?.departments) return []
	return [
		{ label: __('All Departments'), value: '' },
		...filters.data.departments.map((d) => ({ label: d, value: d })),
	]
})

const designationOptions = computed(() => {
	if (!filters.data?.designations) return []
	return [
		{ label: __('All Designations'), value: '' },
		...filters.data.designations.map((d) => ({ label: d, value: d })),
	]
})

const roleProfileOptions = computed(() => {
	if (!filters.data?.role_profiles) return []
	return filters.data.role_profiles.map((rp) => ({ label: rp, value: rp }))
})

const prevPage = () => {
	currentStart.value = Math.max(0, currentStart.value - pageSize)
	loadEmployees()
}

const nextPage = () => {
	currentStart.value += pageSize
	loadEmployees()
}

const openRoleModal = (emp) => {
	selectedEmployee.value = emp
	selectedRoleProfile.value = ''
	showRoleModal.value = true
}

const saveRole = createResource({
	url: 'lms.lms.custom.dashboard_api.save_employee_lms_role',
})

const assignRole = async () => {
	if (!selectedRoleProfile.value || !selectedEmployee.value) return

	try {
		await saveRole.submit({
			employee: selectedEmployee.value.name,
			role_profile: selectedRoleProfile.value.value,
		})
		toast.success(
			saveRole.data?.message || __('Role profile assigned successfully')
		)
		showRoleModal.value = false
		loadEmployees()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to assign role'))
	}
}

// Add Employee Modal
const showAddModal = ref(false)
const newEmployee = reactive({
	employee_name: '',
	gender: '',
	date_of_birth: '',
	user_email: '',
	create_user: true,
	department: '',
	designation: '',
	reports_to: '',
	role_profile: '',
})

const genderOptions = [
	{ label: __('Male'), value: 'Male' },
	{ label: __('Female'), value: 'Female' },
	{ label: __('Other'), value: 'Other' },
]

const allEmployeeOptions = createResource({
	url: 'lms.lms.custom.dashboard_api.get_employee_options',
})

const managerOptions = computed(() => {
	if (!allEmployeeOptions.data) return []
	return allEmployeeOptions.data.map((emp) => ({
		label: `${emp.employee_name} (${emp.name})`,
		value: emp.name,
	}))
})

const openAddModal = () => {
	newEmployee.employee_name = ''
	newEmployee.gender = ''
	newEmployee.date_of_birth = ''
	newEmployee.user_email = ''
	newEmployee.create_user = true
	newEmployee.department = ''
	newEmployee.designation = ''
	newEmployee.reports_to = ''
	newEmployee.role_profile = ''
	allEmployeeOptions.fetch()
	showAddModal.value = true
}

const createEmployee = createResource({
	url: 'lms.lms.custom.dashboard_api.create_employee',
})

const addEmployee = async () => {
	if (!newEmployee.employee_name || !newEmployee.gender || !newEmployee.date_of_birth) return

	try {
		await createEmployee.submit({
			employee_name: newEmployee.employee_name,
			gender: newEmployee.gender?.value || '',
			date_of_birth: newEmployee.date_of_birth || '',
			user_email: newEmployee.user_email || '',
			create_user: newEmployee.create_user ? 1 : 0,
			department: newEmployee.department?.value || '',
			designation: newEmployee.designation?.value || '',
			reports_to: newEmployee.reports_to?.value || '',
			role_profile: newEmployee.role_profile?.value || '',
		})
		toast.success(
			createEmployee.data?.message || __('Employee created successfully')
		)
		showAddModal.value = false
		loadEmployees()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Failed to create employee'))
	}
}
</script>
