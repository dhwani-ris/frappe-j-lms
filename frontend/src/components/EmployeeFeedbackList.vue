<template>
	<div v-if="filtered.length || showEmpty" class="mb-6 rounded-lg border bg-surface-white p-5">
		<div class="mb-3 flex items-center justify-between">
			<div class="font-semibold text-ink-gray-9">{{ heading || __('Employee Feedback') }}</div>
			<Badge
				v-if="pendingCount"
				theme="orange"
				variant="subtle"
				:label="`${pendingCount} ${__('need your feedback')}`"
			/>
		</div>
		<!-- Filters (dedicated /feedback page only) -->
		<div v-if="showFilters && (resource.data || []).length" class="mb-4 flex flex-wrap gap-3">
			<FormControl
				type="select"
				v-model="courseFilter"
				:options="courseOptions"
				:placeholder="__('All Courses')"
				class="w-52"
			/>
			<FormControl
				type="select"
				v-model="managerFilter"
				:options="managerOptions"
				:placeholder="__('All Managers')"
				class="w-52"
			/>
			<FormControl
				type="select"
				v-model="statusFilter"
				:options="statusOptions"
				:placeholder="__('All Statuses')"
				class="w-52"
			/>
			<Button v-if="hasActiveFilters" variant="subtle" @click="clearFilters">
				{{ __('Clear') }}
			</Button>
		</div>

		<div v-if="!filtered.length" class="py-6 text-center text-sm text-ink-gray-5">
			{{ __('No employee feedback forms found.') }}
		</div>
		<div
			v-for="f in filtered"
			:key="f.name"
			class="flex cursor-pointer items-center justify-between border-t py-3 first:border-t-0 first:pt-0 hover:bg-surface-gray-1"
			@click="open(f.name)"
		>
			<div>
				<div class="font-medium text-ink-gray-8">{{ f.employee_name }}</div>
				<div class="text-sm text-ink-gray-5">{{ f.course_title }}</div>
			</div>
			<div class="flex items-center gap-2">
				<Badge
					v-if="f.action_needed"
					theme="orange"
					variant="subtle"
					:label="__('Action needed')"
				/>
				<Badge :theme="statusTheme(f.status)" variant="subtle" :label="__(f.status)" />
				<ChevronRight class="size-4 text-ink-gray-4" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, FormControl, createResource } from 'frappe-ui'
import { ChevronRight } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
	heading: String,
	// Optional role filter: 'manager' | 'trainer' | 'master'. Omit to show all the user can see.
	role: String,
	// Optional: restrict to a single employee (used on the HR Employee Detail page).
	employee: String,
	// Render the card with an empty-state message when there are no rows (for the
	// dedicated /feedback page); dashboards leave this false so the card auto-hides.
	showEmpty: Boolean,
	// Show the Course / Manager / Status filter bar (dedicated /feedback page).
	showFilters: Boolean,
})

const router = useRouter()

const resource = createResource({
	url: 'lms.lms.custom.employee_feedback.list_my_feedback_forms',
	auto: true,
})

const courseFilter = ref('')
const managerFilter = ref('')
const statusFilter = ref('')

const STATUSES = [
	'Draft',
	'Sessions Scheduled',
	'Manager Feedback Added',
	'Trainer Feedback Added',
	'Completed',
]

function uniqueOptions(allLabel, keyField, labelField) {
	const seen = new Map()
	for (const f of resource.data || []) {
		if (f[keyField] && !seen.has(f[keyField])) {
			seen.set(f[keyField], f[labelField] || f[keyField])
		}
	}
	return [
		{ label: __(allLabel), value: '' },
		...[...seen].map(([value, label]) => ({ label, value })),
	]
}

const courseOptions = computed(() =>
	uniqueOptions('All Courses', 'course', 'course_title')
)
const managerOptions = computed(() =>
	uniqueOptions('All Managers', 'immediate_manager', 'immediate_manager_name')
)
const statusOptions = computed(() => {
	const present = new Set((resource.data || []).map((f) => f.status))
	return [
		{ label: __('All Statuses'), value: '' },
		...STATUSES.filter((s) => present.has(s)).map((s) => ({ label: __(s), value: s })),
	]
})

const hasActiveFilters = computed(
	() => !!(courseFilter.value || managerFilter.value || statusFilter.value)
)

function clearFilters() {
	courseFilter.value = ''
	managerFilter.value = ''
	statusFilter.value = ''
}

const filtered = computed(() => {
	let rows = resource.data || []
	if (props.employee) rows = rows.filter((f) => f.employee === props.employee)
	if (props.role === 'manager') rows = rows.filter((f) => f.is_manager)
	else if (props.role === 'trainer') rows = rows.filter((f) => f.is_trainer)
	else if (props.role === 'master') rows = rows.filter((f) => f.is_master)
	if (props.showFilters) {
		if (courseFilter.value) rows = rows.filter((f) => f.course === courseFilter.value)
		if (managerFilter.value)
			rows = rows.filter((f) => f.immediate_manager === managerFilter.value)
		if (statusFilter.value) rows = rows.filter((f) => f.status === statusFilter.value)
	}
	// Surface action-needed items first.
	return [...rows].sort((a, b) => Number(b.action_needed) - Number(a.action_needed))
})

const pendingCount = computed(() => filtered.value.filter((f) => f.action_needed).length)

function statusTheme(status) {
	const map = {
		Draft: 'gray',
		'Manager Feedback Added': 'orange',
		'Trainer Feedback Added': 'orange',
		Completed: 'green',
	}
	return map[status] || 'gray'
}

function open(name) {
	router.push({ name: 'EmployeeFeedbackForm', params: { name } })
}

defineExpose({ reload: () => resource.reload() })
</script>
