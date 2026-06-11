<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Home'), route: { name: 'Home' } },
					{ label: __('Employee Feedback'), route: { name: 'EmployeeFeedback' } },
					{ label: form?.employee_name || feedbackName },
				]"
			/>
			<div class="flex items-center gap-2">
				<Button
					v-if="form?.can_reschedule"
					variant="subtle"
					:loading="saving === 'reschedule'"
					@click="reschedule"
				>
					{{ __('Reschedule') }}
				</Button>
				<Badge v-if="form" :theme="statusTheme" variant="subtle" :label="__(form.status)" />
			</div>
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
						<div class="text-ink-gray-4">{{ __('Master Trainer') }}</div>
						<div class="text-ink-gray-8">{{ form.master_trainer || '—' }}</div>
					</div>
				</div>
			</div>

			<!-- Schedule panel (Master Trainer / admin, before scheduling is confirmed) -->
			<div v-if="form.can_schedule" class="mb-6 rounded-lg border border-blue-200 bg-surface-blue-1 p-5">
				<div class="mb-1 font-semibold text-ink-gray-9">{{ __('Schedule feedback sessions') }}</div>
				<p class="mb-4 text-sm text-ink-gray-6">
					{{
						__(
							'Set each meeting time. Order must be manager → trainers (in order) → master, at least 15 minutes apart, all in the future.'
						)
					}}
				</p>

				<div v-if="form.immediate_manager" class="mb-3">
					<label class="mb-1 block text-sm text-ink-gray-7">
						{{ __('Manager') }} — {{ form.immediate_manager_name }}
					</label>
					<input type="datetime-local" v-model="sched.manager" class="form-input w-full" />
				</div>

				<div v-for="t in form.trainers" :key="t.name" class="mb-3">
					<label class="mb-1 block text-sm text-ink-gray-7">
						{{ __('Trainer') }} — {{ t.trainer_name || t.trainer }}
					</label>
					<input
						type="datetime-local"
						v-model="sched.trainers[t.name]"
						class="form-input w-full"
					/>
				</div>

				<div class="mb-4">
					<label class="mb-1 block text-sm text-ink-gray-7">
						{{ __('Master Trainer') }} ({{ __('you') }})
					</label>
					<input type="datetime-local" v-model="sched.master" class="form-input w-full" />
				</div>

				<Button variant="solid" :loading="saving === 'schedule'" @click="confirmSchedule">
					{{ __('Confirm Schedule') }}
				</Button>
			</div>

			<!-- Not yet scheduled, and the viewer can't schedule -->
			<div
				v-else-if="!form.sessions_scheduled"
				class="mb-6 rounded-lg border bg-surface-gray-1 p-5 text-sm text-ink-gray-6"
			>
				{{ __('Feedback will open once the master trainer schedules the sessions.') }}
			</div>

			<!-- Feedback sections (only once scheduled) -->
			<template v-if="form.sessions_scheduled">
				<!-- Manager Feedback -->
				<FeedbackBlock
					v-if="form.immediate_manager"
					:title="__('Manager Feedback')"
					:recorded="!!form.manager_feedback_done"
					:recorded-by="form.manager_feedback_by"
					:recorded-on="form.manager_feedback_on"
					:editable="form.can_edit_manager"
					:scheduled-datetime="form.manager_meeting_datetime"
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
								<Badge v-if="row.is_me" theme="blue" variant="subtle" :label="__('You')" />
							</div>
							<Badge
								:theme="row.recorded ? 'green' : 'gray'"
								variant="subtle"
								:label="row.recorded ? __('Recorded') : __('Pending')"
							/>
						</div>
						<div class="mb-2 text-sm text-ink-gray-6">
							<span class="text-ink-gray-4">{{ __('Scheduled') }}:</span>
							{{ row.meeting_datetime || __('Not scheduled yet') }}
						</div>

						<!-- Editable: the current user's own row -->
						<div v-if="row.is_me && form.can_edit_trainer" class="space-y-2">
							<FormControl
								type="textarea"
								:rows="4"
								v-model="trainerFeedback"
								:placeholder="__('Your feedback after the mock session…')"
							/>
							<Button variant="solid" :loading="saving === 'trainer'" @click="saveTrainer">
								{{ __('Save Trainer Feedback') }}
							</Button>
						</div>

						<!-- Read-only -->
						<div v-else>
							<div
								v-if="row.feedback"
								class="prose prose-sm max-w-none text-ink-gray-7"
								v-html="row.feedback"
							/>
							<div v-else class="text-sm text-ink-gray-4">{{ __('Not recorded yet.') }}</div>
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
					:scheduled-datetime="form.master_meeting_datetime"
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
			</template>
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
const trainerFeedback = ref('')
const sched = reactive({ manager: '', master: '', trainers: {} })

const resource = createResource({
	url: 'lms.lms.custom.employee_feedback.get_feedback_form',
	params: { name: feedbackName },
	auto: true,
})

const form = computed(() => resource.data)

const statusTheme = computed(() => {
	const map = {
		Draft: 'gray',
		'Sessions Scheduled': 'blue',
		'Manager Feedback Added': 'orange',
		'Trainer Feedback Added': 'orange',
		Completed: 'green',
	}
	return map[form.value?.status] || 'gray'
})

const recordedTrainers = computed(
	() => form.value?.trainers.filter((t) => t.recorded).length || 0
)

// Seed editable + schedule fields once data arrives.
watch(form, (f) => {
	if (!f) return
	const myRow = f.trainers.find((t) => t.is_me)
	trainerFeedback.value = stripHtml(myRow?.feedback)

	sched.manager = toLocalInput(f.manager_meeting_datetime)
	sched.master = toLocalInput(f.master_meeting_datetime)
	sched.trainers = {}
	for (const t of f.trainers) {
		sched.trainers[t.name] = toLocalInput(t.meeting_datetime)
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

function confirmSchedule() {
	const trainer_times = form.value.trainers.map((t) => ({
		row: t.name,
		meeting_datetime: toServer(sched.trainers[t.name]),
	}))
	return runAction(
		'schedule_sessions',
		{
			name: feedbackName,
			manager_meeting_datetime: toServer(sched.manager),
			master_meeting_datetime: toServer(sched.master),
			trainer_times,
		},
		'schedule'
	)
}
function reschedule() {
	return runAction('reschedule_sessions', { name: feedbackName }, 'reschedule')
}
function saveManager(payload) {
	return runAction('save_manager_feedback', { name: feedbackName, feedback: payload.feedback }, 'manager')
}
function saveMaster(payload) {
	return runAction('save_master_feedback', { name: feedbackName, feedback: payload.feedback }, 'master')
}
function saveTrainer() {
	return runAction('save_trainer_feedback', { name: feedbackName, feedback: trainerFeedback.value }, 'trainer')
}
function complete() {
	return runAction('complete_feedback', { name: feedbackName }, 'complete')
}
function reopen() {
	return runAction('reopen_feedback', { name: feedbackName }, 'reopen')
}
</script>
