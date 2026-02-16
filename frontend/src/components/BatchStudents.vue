<template>
	<div>
		<div class="flex items-center justify-between mb-4">
			<div class="text-ink-gray-9 font-medium">
				{{ studentCount.data ?? 0 }} {{ __('Students') }}
			</div>
			<Button v-if="!readOnlyMode" @click="openStudentModal()">
				<template #prefix>
					<Plus class="h-4 w-4" />
				</template>
				{{ __('Add') }}
			</Button>
		</div>

		<div v-if="students.data?.length">
			<ListView
				class="max-h-[75vh]"
				:columns="studentColumns"
				:rows="students.data"
				row-key="name"
				:options="{
					showTooltip: false,
				}"
			>
				<ListHeader
					class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
				>
					<ListHeaderItem
						:item="item"
						v-for="item in studentColumns"
						:title="item.label"
					>
						<template #prefix="{ item }">
							<FeatherIcon
								v-if="item.icon"
								:name="item.icon"
								class="h-4 w-4 stroke-1.5"
							/>
						</template>
					</ListHeaderItem>
				</ListHeader>
				<ListRows>
					<ListRow
						:row="row"
						v-for="row in students.data"
						class="group hover:bg-surface-gray-2 rounded"
					>
						<template #default="{ column, item }">
							<ListRowItem
								:item="row[column.key]"
								:align="column.align"
								class="text-sm"
								:class="{ 'cursor-pointer': column.key !== 'actions' && column.key !== 'approval_status' }"
								@click="column.key !== 'actions' && column.key !== 'approval_status' ? openStudentProgressModal(row) : null"
							>
								<template #prefix>
									<div v-if="column.key == 'full_name'">
										<Avatar
											class="flex items-center"
											:image="row['user_image']"
											:label="item"
											size="sm"
										/>
									</div>
								</template>
								<div
									v-if="column.key == 'progress'"
									class="flex items-center space-x-4 w-full"
								>
									<ProgressBar :progress="row[column.key]" size="sm" />
									<div class="text-xs">{{ row[column.key] }}%</div>
								</div>
								<div v-else-if="column.key == 'approval_status'">
									<Badge
										:theme="
											row.approval_status === 'Approved'
												? 'green'
												: row.approval_status === 'Rejected'
												? 'red'
												: 'orange'
										"
										size="sm"
									>
										{{ row.approval_status || 'Pending' }}
									</Badge>
								</div>
								<div
									v-else-if="column.key == 'manager_comments'"
									class="text-sm text-ink-gray-8"
									:title="stripHtml(row.manager_comments)"
								>
									<span v-if="row.manager_comments" class="line-clamp-2">
										{{ stripHtml(row.manager_comments) }}
									</span>
									<span v-else class="text-ink-gray-5 italic">
										No remarks
									</span>
								</div>
								<div
									v-else-if="column.key == 'actions' && canApproveStudents && row.progress === 100 && row.member !== userResource.data?.name"
									class="flex justify-center gap-1"
									@click.stop
								>
									<Button
										size="sm"
										variant="solid"
										theme="green"
										@click="openRemarksDialog(row, 'approve')"
									>
										Approve
									</Button>
									<Button
										size="sm"
										variant="solid"
										theme="red"
										@click="openRemarksDialog(row, 'reject')"
									>
										Reject
									</Button>
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</ListRows>
				<ListSelectBanner>
					<template #actions="{ unselectAll, selections }">
						<div class="flex gap-2">
							<Button
								variant="ghost"
								@click="removeStudents(selections, unselectAll)"
							>
								<Trash2 class="h-4 w-4 stroke-1.5" />
							</Button>
						</div>
					</template>
				</ListSelectBanner>
				<div class="mt-4 flex justify-center" v-if="students.hasNextPage">
					<Button @click="students.next()">
						{{ __('Load More') }}
					</Button>
				</div>
			</ListView>
		</div>
		<div v-else-if="!students.loading" class="text-sm italic text-ink-gray-5">
			{{ __('There are no students in this batch.') }}
		</div>
	</div>

	<StudentModal
		:batch="props.batch.data.name"
		v-model="showStudentModal"
		v-model:reloadStudents="students"
		v-model:batchModal="props.batch"
	/>
	<BatchStudentProgress
		:student="selectedStudent"
		v-model="showStudentProgressModal"
	/>
	<Dialog
		v-model="showRemarksDialog"
		:options="{
			title: currentAction === 'approve' ? 'Approve Student' : 'Reject Student',
			size: 'xl',
			actions: [
				{
					label: currentAction === 'approve' ? 'Approve' : 'Reject',
					variant: 'solid',
					theme: currentAction === 'approve' ? 'green' : 'red',
					onClick: () => saveRemarks(),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<div>
					<label class="block text-sm font-medium text-ink-gray-9 mb-2">
						Add remarks (optional):
					</label>
					<TextEditor
						:content="currentRemarks"
						:editable="true"
						editor-class="min-h-[200px] prose-sm"
						@change="(val) => currentRemarks = val"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Avatar,
	Button,
	createListResource,
	createResource,
	FeatherIcon,
	ListHeader,
	ListHeaderItem,
	ListSelectBanner,
	ListRow,
	ListRows,
	ListView,
	ListRowItem,
	toast,
	Badge,
	TextEditor,
	Dialog,
} from 'frappe-ui'
import { Plus, Trash2 } from 'lucide-vue-next'
import { ref, computed } from 'vue'
import { usersStore } from '@/stores/user'
import StudentModal from '@/components/Modals/StudentModal.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import BatchStudentProgress from '@/components/Modals/BatchStudentProgress.vue'

const showStudentModal = ref(false)
const showStudentProgressModal = ref(false)
const selectedStudent = ref(null)
const readOnlyMode = window.read_only_mode
const { userResource } = usersStore()
const showRemarksDialog = ref(false)
const currentRemarks = ref('')
const currentStudentForRemarks = ref(null)
const currentAction = ref('') // 'approve' or 'reject'

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})

const studentCount = createResource({
	url: 'lms.lms.utils.get_batch_students_count',
	cache: ['batch_student_count', props.batch?.data?.name],
	params: {
		batch: props.batch?.data?.name,
	},
	auto: true,
})

const students = createListResource({
	doctype: 'LMS Batch Enrollment',
	url: 'lms.lms.utils.get_batch_students',
	pageLength: 50,
	filters: {
		batch: props.batch?.data?.name,
	},
	auto: true,
})

const canApproveStudents = computed(() => {
	// Check for System Manager boolean flag (fast check)
	if (userResource.data?.is_system_manager) {
		return true
	}

	// Check if Administrator
	if (userResource.data?.name === 'Administrator') {
		return true
	}

	// Check if Moderator or Course Creator
	if (userResource.data?.is_moderator || userResource.data?.is_instructor) {
		return true
	}

	// Check roles array for Manager or Leave Approver
	const hasManagerRole = userResource.data?.roles?.includes('Manager')
	const hasLeaveApproverRole = userResource.data?.roles?.includes('Leave Approver')

	// If user can see students in the list, they should be able to approve
	// The backend will validate actual permissions based on employee hierarchy
	// So we allow showing buttons, and backend will reject if unauthorized
	return hasManagerRole || hasLeaveApproverRole || students.data?.length > 0
})

const studentColumns = computed(() => {
	const baseColumns = [
		{
			label: 'Full Name',
			key: 'full_name',
			width: '18rem',
			icon: 'user',
		},
		{
			label: 'Progress',
			key: 'progress',
			width: '10rem',
			icon: 'activity',
		},
		{
			label: 'Last Active',
			key: 'last_active',
			width: '8rem',
			align: 'center',
			icon: 'clock',
		},
	]

	if (canApproveStudents.value) {
		baseColumns.push(
			{
				label: 'Status',
				key: 'approval_status',
				width: '7rem',
				align: 'center',
			},
			{
				label: 'Actions',
				key: 'actions',
				width: '10rem',
				align: 'center',
			},
			{
				label: 'Remarks',
				key: 'manager_comments',
				width: '20rem',
			}
		)
	}

	return baseColumns
})

const stripHtml = (html) => {
	if (!html) return ''
	const tmp = document.createElement('DIV')
	tmp.innerHTML = html
	return tmp.textContent || tmp.innerText || ''
}

const openStudentModal = () => {
	showStudentModal.value = true
}

const openStudentProgressModal = (row) => {
	showStudentProgressModal.value = true
	selectedStudent.value = row
}

const deleteStudents = createResource({
	url: 'lms.lms.api.delete_documents',
	makeParams(values) {
		return {
			doctype: 'LMS Batch Enrollment',
			documents: values.students,
		}
	},
})

const removeStudents = (selections, unselectAll) => {
	deleteStudents.submit(
		{
			students: Array.from(selections),
		},
		{
			onSuccess(data) {
				students.reload()
				studentCount.reload()
				props.batch.reload()
				toast.success(__('Students deleted successfully'))
				unselectAll()
			},
		}
	)
}

const approveEnrollmentResource = createResource({
	url: 'lms.lms.custom.batch_enrollment_approval.approve_enrollment',
	makeParams(values) {
		return {
			name: values.name,
			comments: values.comments,
		}
	},
})

const rejectEnrollmentResource = createResource({
	url: 'lms.lms.custom.batch_enrollment_approval.reject_enrollment',
	makeParams(values) {
		return {
			name: values.name,
			comments: values.comments,
		}
	},
})

const openRemarksDialog = (row, action) => {
	currentStudentForRemarks.value = row
	currentRemarks.value = row.manager_comments || ''
	currentAction.value = action
	showRemarksDialog.value = true
}

const saveRemarks = () => {
	if (!currentStudentForRemarks.value) return

	if (currentAction.value === 'approve') {
		approveEnrollment(currentStudentForRemarks.value)
	} else if (currentAction.value === 'reject') {
		rejectEnrollment(currentStudentForRemarks.value)
	}
}

const approveEnrollment = (row) => {
	approveEnrollmentResource.submit(
		{
			name: row.name,
			comments: currentRemarks.value || null,
		},
		{
			onSuccess(data) {
				students.reload()
				toast.success(data.message || __('Enrollment approved successfully'))
				showRemarksDialog.value = false
				currentRemarks.value = ''
			},
			onError(error) {
				toast.error(error.messages?.[0] || __('Failed to approve enrollment'))
			},
		}
	)
}

const rejectEnrollment = (row) => {
	rejectEnrollmentResource.submit(
		{
			name: row.name,
			comments: currentRemarks.value || null,
		},
		{
			onSuccess(data) {
				students.reload()
				toast.success(data.message || __('Enrollment rejected'))
				showRemarksDialog.value = false
				currentRemarks.value = ''
			},
			onError(error) {
				toast.error(error.messages?.[0] || __('Failed to reject enrollment'))
			},
		}
	)
}
</script>
