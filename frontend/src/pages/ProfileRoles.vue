<template>
	<div class="mt-7">
		<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
			{{ __('Settings') }}
		</h2>
		<div
			v-if="readOnlyMode"
			class="flex items-center space-x-2 text-sm text-ink-gray-7 bg-surface-gray-1 px-3 py-2 rounded-md w-full text-center"
		>
			<CircleAlert class="size-4 stroke-1.5" />
			<span>
				{{ __('You cannot change the roles in read-only mode.') }}
			</span>
		</div>
		<div v-else>
			<div
				class="flex flex-col md:flex-row gap-4 md:gap-0 justify-between w-3/4 mt-5"
			>
				<FormControl
					:label="__('Moderator')"
					v-model="roleRefs.moderator"
					type="checkbox"
					@change.stop="changeRole('moderator')"
				/>
				<FormControl
					:label="__('Course Creator')"
					v-model="roleRefs.course_creator"
					type="checkbox"
					@change.stop="changeRole('course_creator')"
				/>
				<FormControl
					:label="__('Evaluator')"
					v-model="roleRefs.batch_evaluator"
					type="checkbox"
					@change.stop="changeRole('batch_evaluator')"
				/>
				<FormControl
					:label="__('Student')"
					v-model="roleRefs.lms_student"
					type="checkbox"
					@change.stop="changeRole('lms_student')"
				/>
			</div>

			<!-- Jamboree LMS Roles -->
			<h3 class="mt-6 mb-3 text-md font-semibold text-ink-gray-7">
				{{ __('Jamboree Roles') }}
			</h3>
			<div
				class="flex flex-col md:flex-row gap-4 md:gap-0 justify-between w-3/4"
			>
				<FormControl
					:label="__('LMS Trainer')"
					v-model="roleRefs.lms_trainer"
					type="checkbox"
					@change.stop="changeRole('lms_trainer')"
				/>
				<FormControl
					:label="__('LMS Master Trainer')"
					v-model="roleRefs.lms_master_trainer"
					type="checkbox"
					@change.stop="changeRole('lms_master_trainer')"
				/>
				<FormControl
					:label="__('LMS Manager')"
					v-model="roleRefs.lms_manager"
					type="checkbox"
					@change.stop="changeRole('lms_manager')"
				/>
				<FormControl
					:label="__('LMS HR')"
					v-model="roleRefs.lms_hr"
					type="checkbox"
					@change.stop="changeRole('lms_hr')"
				/>
			</div>
		</div>
	</div>
</template>
<script setup>
import { FormControl, createResource, toast } from 'frappe-ui'
import { reactive, watch } from 'vue'
import { CircleAlert } from 'lucide-vue-next'

const readOnlyMode = window.read_only_mode

// Use reactive object instead of eval() for safe dynamic access
const roleRefs = reactive({
	moderator: false,
	course_creator: false,
	batch_evaluator: false,
	lms_student: false,
	lms_trainer: false,
	lms_master_trainer: false,
	lms_manager: false,
	lms_hr: false,
})

// Map from internal key to Frappe role name
const roleNameMap = {
	moderator: 'Moderator',
	course_creator: 'Course Creator',
	batch_evaluator: 'Batch Evaluator',
	lms_student: 'LMS Student',
	lms_trainer: 'LMS Trainer',
	lms_master_trainer: 'LMS Master Trainer',
	lms_manager: 'LMS Manager',
	lms_hr: 'LMS HR',
}

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const roles = createResource({
	url: 'lms.lms.utils.get_roles',
	makeParams(values) {
		return {
			name: values.member,
		}
	},
	onSuccess(data) {
		for (let roleKey of Object.keys(roleRefs)) {
			roleRefs[roleKey] = !!data[roleKey]
		}
	},
})

watch(
	() => props.profile,
	(newValue) => {
		roles.reload({
			member: newValue.data?.name,
		})
	},
	{ immediate: true }
)

const updateRole = createResource({
	url: 'lms.lms.api.save_role',
	makeParams(values) {
		return {
			user: props.profile.data?.name,
			role: values.role,
			value: values.value,
		}
	},
})

const changeRole = (roleKey) => {
	updateRole.submit(
		{
			role: roleNameMap[roleKey],
			value: roleRefs[roleKey],
		},
		{
			onSuccess() {
				toast.success(__('Role updated successfully'))
			},
		}
	)
}
</script>
