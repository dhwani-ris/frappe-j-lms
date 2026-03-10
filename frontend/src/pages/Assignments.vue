<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button
			v-if="!readOnlyMode && (user.data?.is_moderator || user.data?.is_instructor || user.data?.is_master_trainer || user.data?.is_lms_hr)"
			variant="solid"
			@click="
				() => {
					assignmentID = 'new'
					showAssignmentForm = true
				}
			"
		>
			<template #prefix>
				<Plus class="w-4 h-4" />
			</template>
			{{ __('Create') }}
		</Button>
	</header>

	<div class="py-5 mx-5">
		<div class="flex items-center justify-between mb-4">
			<div class="text-lg font-semibold text-ink-gray-7">
				{{
					assignments.data?.length
						? __('{0} Assignments').format(assignments.data.length)
						: __('No Assignments')
				}}
			</div>
			<div class="flex gap-3">
				<FormControl
					v-model="titleFilter"
					type="text"
					:placeholder="__('Search')"
				>
					<template #prefix>
						<FeatherIcon name="search" class="size-4 text-ink-gray-5" />
					</template>
				</FormControl>
				<FormControl
					v-model="typeFilter"
					type="select"
					:options="assignmentTypes"
					:placeholder="__('Type')"
				/>
			</div>
		</div>
		<ListView
			v-if="assignments.data?.length"
			:columns="assignmentColumns"
			:rows="assignments.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: true }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in assignmentColumns" :key="item.key">
					<template #prefix="{ item }">
						<FeatherIcon :name="item.icon?.toString()" class="h-4 w-4" />
					</template>
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<div
					v-for="row in assignments.data"
					:key="row.name"
					@click="!readOnlyMode && (user.data?.is_moderator || user.data?.is_instructor || user.data?.is_master_trainer || user.data?.is_lms_hr) && openAssignment(row.name)"
					:class="!readOnlyMode && (user.data?.is_moderator || user.data?.is_instructor || user.data?.is_master_trainer || user.data?.is_lms_hr) ? 'cursor-pointer' : 'cursor-default'"
				>
					<ListRow :row="row">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div
									v-if="column.key == 'creation'"
									class="text-xs text-ink-gray-5"
								>
									{{ row[column.key] }}
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</div>
			</ListRows>
			<ListSelectBanner>
				<template #actions="{ unselectAll, selections }">
					<div class="flex gap-2">
						<Button
							variant="ghost"
							@click="deleteAssignments(selections, unselectAll)"
						>
							<FeatherIcon name="trash-2" class="h-4 w-4 stroke-1.5" />
						</Button>
					</div>
				</template>
			</ListSelectBanner>
		</ListView>
		<EmptyState v-else type="Assignments" />
		<div v-if="assignments.hasNextPage" class="flex justify-center my-5">
			<Button @click="assignments.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<AssignmentForm
		v-model="showAssignmentForm"
		v-model:assignments="assignments"
		:assignmentID="assignmentID"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createListResource,
	FeatherIcon,
	FormControl,
	ListView,
	ListRows,
	ListRow,
	ListRowItem,
	ListHeader,
	ListHeaderItem,
	ListSelectBanner,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import { useRouter, useRoute } from 'vue-router'
import { sessionStore } from '../stores/session'
import AssignmentForm from '@/components/Modals/AssignmentForm.vue'
import EmptyState from '@/components/EmptyState.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const router = useRouter()
const route = useRoute()
const titleFilter = ref('')
const typeFilter = ref('')
const showAssignmentForm = ref(false)
const assignmentID = ref('new')
const readOnlyMode = window.read_only_mode

const assignmentFilters = ref({})

const initAssignments = () => {
	const userData = user.data
	if (!userData) return false
	if (!userData.is_moderator && !userData.is_instructor && !userData.is_trainer && !userData.is_master_trainer) {
		router.push({ name: 'Courses' })
		return true
	}
	delete assignmentFilters.value['owner']
	assignments.update({ filters: { ...assignmentFilters.value } })
	assignments.reload()
	return true
}

onMounted(() => {
	if (route.query.new === 'true') {
		assignmentID.value = 'new'
		showAssignmentForm.value = true
	}
	if (!initAssignments()) {
		// user.data not ready yet, watch for it
		const stop = watch(() => user.data, (userData) => {
			if (!userData) return
			initAssignments()
			stop()
		})
	}
})

watch(titleFilter, () => {
	assignmentFilters.value['title'] = ['like', `%${titleFilter.value}%`]
	assignments.update({
		filters: assignmentFilters.value,
	})
	assignments.reload()
})

watch(typeFilter, () => {
	if (typeFilter.value) {
		assignmentFilters.value['type'] = typeFilter.value
	} else {
		delete assignmentFilters.value['type']
	}
	assignments.update({
		filters: assignmentFilters.value,
	})
	assignments.reload()
})

const assignments = createListResource({
	doctype: 'LMS Assignment',
	filters: assignmentFilters,
	fields: ['name', 'title', 'type', 'creation'],
	auto: false,
	cache: ['assignments', user.data?.name],
	orderBy: 'modified desc',
	transform(data) {
		return data.map((assignment) => {
			return {
				...assignment,
				creation: dayjs(assignment.creation).fromNow(),
			}
		})
	},
})

const openAssignment = (name) => {
	assignmentID.value = name
	showAssignmentForm.value = true
}

const deleteAssignments = async (selections, unselectAll) => {
	try {
		// Wait for all deletions to complete
		const deletePromises = Array.from(selections).map(assignmentName =>
			call('lms.lms.api.delete_assignment', {
				assignment_name: assignmentName
			})
		)

		await Promise.all(deletePromises)
		unselectAll()
		toast.success(__('Assignments deleted successfully'))
		await assignments.reload()
	} catch (error) {
		console.error('Error deleting assignments:', error)
		toast.error(__('Error deleting assignments'))
	}
}

const assignmentColumns = computed(() => {
	return [
		{
			label: __('Title'),
			key: 'title',
			width: 2,
			icon: 'file-text',
		},
		{
			label: __('Type'),
			key: 'type',
			width: 1,
			align: 'center',
			icon: 'tag',
		},
		{
			label: __('Created'),
			key: 'creation',
			width: 1,
			align: 'center',
			icon: 'clock',
		},
	]
})

const assignmentTypes = computed(() => {
	let types = ['', 'Document', 'Image', 'PDF', 'URL', 'Text']
	return types.map((type) => {
		return {
			label: type ? __(type) : __('All Types'),
			value: type,
		}
	})
})

const breadcrumbs = computed(() => {
	return [
		{
			label: __('Assignments'),
			route: {
				name: 'Assignments',
			},
		},
	]
})

usePageMeta(() => {
	return {
		title: __('Assignments'),
		icon: brand.favicon,
	}
})
</script>
