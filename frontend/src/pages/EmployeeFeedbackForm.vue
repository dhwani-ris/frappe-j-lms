<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Employee Feedback') },
					{ label: form?.employee_name || feedbackName },
				]"
			/>
			<Badge v-if="form" :theme="statusTheme" variant="subtle" :label="__(form.status)" />
		</header>

		<div v-if="resource.loading" class="flex items-center justify-center py-20">
			<LoadingIndicator class="size-8" />
		</div>

		<div v-else-if="form" class="mx-auto max-w-3xl p-5">
			<!-- Summary -->
			<div class="mb-6 rounded-lg border bg-surface-white p-5">
				<div class="text-lg font-semibold text-ink-gray-9">
					{{ form.employee_name }}
				</div>
				<div class="mt-1 text-ink-gray-6">{{ form.course_title }}</div>
				<div class="mt-3 grid grid-cols-2 gap-3 text-sm text-ink-gray-6 sm:grid-cols-3">
					<div>
						<div class="text-ink-gray-4">{{ __('Completed On') }}</div>
						<div class="text-ink-gray-8">{{ form.completed_on || '—' }}</div>
					</div>
					<div>
						<div class="text-ink-gray-4">{{ __('Immediate Manager') }}</div>
						<div class="text-ink-gray-8">{{ form.immediate_manager_name || '—' }}</div>
					</div>
					<div>
						<div class="text-ink-gray-4">{{ __('Batch') }}</div>
						<div class="text-ink-gray-8">{{ form.batch || '—' }}</div>
					</div>
				</div>
			</div>

			<!-- Manager Feedback -->
			<FeedbackBlock
				:title="__('Manager Feedback')"
				:recorded="!!form.manager_feedback_done"
				:recorded-by="form.manager_feedback_by"
				:recorded-on="form.manager_feedback_on"
				:editable="form.can_edit_manager"
				:datetime="managerEdit.datetime"
				:feedback="form.manager_feedback"
				:saving="saving === 'manager'"
				@save="(p) => saveManager(p)"
			/>

			<!-- Trainer Feedback -->
			<div class="mb-6 rounded-lg border bg-surface-white p-5">
				<div class="mb-3 flex items-center justify-between">
					<div class="font-semibold text-ink-gray-9">{{ __('Trainer Feedback') }}</div>
					<span class="text-sm text-ink-gray-5">
						{{ recordedTrainers }}/{{ form.trainers.length }} {{ __('recorded') }}
					</span>
				</div>
				<div v-if="!form.trainers.length" class="text-sm text-ink-gray-5">
					{{ __('No trainers assigned.') }}
				</div>
				<div
					v-for="row in form.trainers"
					:key="row.trainer"
					class="border-t py-4 first:border-t-0 first:pt-0"
				>
					<div class="mb-2 flex items-center justify-between">
						<div class="flex items-center gap-2">
							<span class="font-medium text-ink-gray-8">
								{{ row.trainer_name || row.trainer }}
							</span>
							<Badge
								v-if="row.is_me"
								theme="blue"
								variant="subtle"
								:label="__('You')"
							/>
						</div>
						<Badge
							:theme="row.recorded ? 'green' : 'gray'"
							variant="subtle"
							:label="row.recorded ? __('Recorded') : __('Pending')"
						/>
					</div>

					<!-- Editable: the current user's own row -->
					<div v-if="row.is_me && form.can_edit_trainer" class="space-y-2">
						<input
							type="datetime-local"
							v-model="trainerEdit.datetime"
							class="form-input w-full"
						/>
						<FormControl
							type="textarea"
							:rows="4"
							v-model="trainerEdit.feedback"
							:placeholder="__('Your feedback after the mock session…')"
						/>
						<Button
							variant="solid"
							:loading="saving === 'trainer'"
							@click="saveTrainer"
						>
							{{ __('Save Trainer Feedback') }}
						</Button>
					</div>

					<!-- Read-only -->
					<div v-else>
						<div v-if="row.meeting_datetime" class="mb-1 text-xs text-ink-gray-5">
							{{ __('Meeting') }}: {{ row.meeting_datetime }}
						</div>
						<div
							v-if="row.feedback"
							class="prose prose-sm max-w-none text-ink-gray-7"
							v-html="row.feedback"
						/>
						<div v-else class="text-sm text-ink-gray-4">
							{{ __('Not recorded yet.') }}
						</div>
					</div>
				</div>
			</div>

			<!-- Master Trainer Feedback -->
			<FeedbackBlock
				:title="__('Master Trainer Feedback')"
				:recorded="!!form.master_feedback_done"
				:recorded-by="form.master_feedback_by"
				:recorded-on="form.master_feedback_on"
				:editable="form.can_edit_master"
				:datetime="masterEdit.datetime"
				:feedback="form.master_feedback"
				:saving="saving === 'master'"
				@save="(p) => saveMaster(p)"
			/>

			<!-- Actions -->
			<div class="flex items-center justify-end gap-2">
				<Button
					v-if="form.can_reopen"
					variant="subtle"
					:loading="saving === 'reopen'"
					@click="reopen"
				>
					{{ __('Reopen for Corrections') }}
				</Button>
				<Button
					v-if="form.can_edit_master"
					variant="solid"
					:disabled="!form.can_complete"
					:loading="saving === 'complete'"
					@click="complete"
				>
					{{ __('Complete & Submit') }}
				</Button>
			</div>
			<p
				v-if="form.can_edit_master && !form.can_complete && form.status !== 'Completed'"
				class="mt-2 text-right text-xs text-ink-gray-4"
			>
				{{ __('Manager, all trainers and master feedback must be recorded to complete.') }}
			</p>
		</div>

		<div v-else class="p-10 text-center text-ink-gray-5">
			{{ __('Feedback form not found or not accessible.') }}
		</div>
	</div>
</template>

<script setup>
import { Breadcrumbs, Button, Badge, FormControl, LoadingIndicator, createResource, call } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'frappe-ui'
import FeedbackBlock from '@/components/FeedbackBlock.vue'

const route = useRoute()
const feedbackName = route.params.name

const saving = ref(null)
const managerEdit = reactive({ datetime: '' })
const masterEdit = reactive({ datetime: '' })
const trainerEdit = reactive({ datetime: '', feedback: '' })

const resource = createResource({
	url: 'lms.lms.custom.employee_feedback.get_feedback_form',
	params: { name: feedbackName },
	auto: true,
})

const form = computed(() => resource.data)

const statusTheme = computed(() => {
	const map = {
		Draft: 'gray',
		'Manager Feedback Added': 'orange',
		'Trainer Feedback Added': 'orange',
		Completed: 'green',
	}
	return map[form.value?.status] || 'gray'
})

const recordedTrainers = computed(
	() => form.value?.trainers.filter((t) => t.recorded).length || 0
)

// Seed the editable fields once data arrives.
watch(form, (f) => {
	if (!f) return
	managerEdit.datetime = toLocalInput(f.manager_meeting_datetime)
	masterEdit.datetime = toLocalInput(f.master_meeting_datetime)
	const myRow = f.trainers.find((t) => t.is_me)
	if (myRow) {
		trainerEdit.datetime = toLocalInput(myRow.meeting_datetime)
		trainerEdit.feedback = stripHtml(myRow.feedback)
	}
})

function toLocalInput(dt) {
	if (!dt) return ''
	return String(dt).replace(' ', 'T').slice(0, 16)
}
function toServer(dt) {
	if (!dt) return null
	return dt.replace('T', ' ') + (dt.length === 16 ? ':00' : '')
}
function stripHtml(html) {
	if (!html) return ''
	const tmp = document.createElement('div')
	tmp.innerHTML = html
	return (tmp.textContent || tmp.innerText || '').trim()
}

async function runAction(method, args, key) {
	saving.value = key
	try {
		await call(`lms.lms.custom.employee_feedback.${method}`, args)
		toast.success(__('Saved'))
		await resource.reload()
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || __('Something went wrong'))
	} finally {
		saving.value = null
	}
}

function saveManager(payload) {
	managerEdit.datetime = payload.datetime
	return runAction(
		'save_manager_feedback',
		{ name: feedbackName, meeting_datetime: toServer(payload.datetime), feedback: payload.feedback },
		'manager'
	)
}
function saveMaster(payload) {
	masterEdit.datetime = payload.datetime
	return runAction(
		'save_master_feedback',
		{ name: feedbackName, meeting_datetime: toServer(payload.datetime), feedback: payload.feedback },
		'master'
	)
}
function saveTrainer() {
	return runAction(
		'save_trainer_feedback',
		{
			name: feedbackName,
			meeting_datetime: toServer(trainerEdit.datetime),
			feedback: trainerEdit.feedback,
		},
		'trainer'
	)
}
function complete() {
	return runAction('complete_feedback', { name: feedbackName }, 'complete')
}
function reopen() {
	return runAction('reopen_feedback', { name: feedbackName }, 'reopen')
}
</script>
