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
				<div class="text-lg font-semibold text-ink-gray-9">{{ form.employee_name }}</div>
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
			<div
				v-if="form.can_schedule"
				class="mb-6 rounded-lg border border-blue-200 bg-surface-blue-1 p-5"
			>
				<div class="mb-1 font-semibold text-ink-gray-9">{{ __('Schedule feedback sessions') }}</div>
				<p class="mb-4 text-sm text-ink-gray-6">
					{{
						__(
							'Order must be manager sessions → trainers → master sessions, at least 15 minutes apart, all in the future. The manager and master can have multiple sessions.'
						)
					}}
				</p>

				<!-- Manager sessions -->
				<div v-if="form.immediate_manager" class="mb-4">
					<div class="mb-1 flex items-center justify-between">
						<label class="text-sm font-medium text-ink-gray-7">
							{{ __('Manager sessions') }} — {{ form.immediate_manager_name }}
						</label>
						<Button variant="ghost" @click="addRow('manager')">
							<template #prefix><Plus class="size-4" /></template>
							{{ __('Add') }}
						</Button>
					</div>
					<div v-for="(s, i) in sched.manager" :key="i" class="mb-2 flex items-center gap-2">
						<input type="datetime-local" v-model="s.dt" class="form-input w-full" />
						<Button
							variant="ghost"
							:disabled="sched.manager.length === 1"
							@click="removeRow('manager', i)"
						>
							<Trash2 class="size-4 text-ink-gray-6" />
						</Button>
					</div>
				</div>

				<!-- Trainer sessions (fixed rows) -->
				<div v-for="t in form.trainers" :key="t.name" class="mb-3">
					<label class="mb-1 block text-sm font-medium text-ink-gray-7">
						{{ __('Trainer') }} — {{ t.trainer_name || t.trainer }}
					</label>
					<input type="datetime-local" v-model="sched.trainers[t.name]" class="form-input w-full" />
				</div>

				<!-- Master sessions -->
				<div class="mb-4">
					<div class="mb-1 flex items-center justify-between">
						<label class="text-sm font-medium text-ink-gray-7">
							{{ __('Master trainer sessions') }} ({{ __('you') }})
						</label>
						<Button variant="ghost" @click="addRow('master')">
							<template #prefix><Plus class="size-4" /></template>
							{{ __('Add') }}
						</Button>
					</div>
					<div v-for="(s, i) in sched.master" :key="i" class="mb-2 flex items-center gap-2">
						<input type="datetime-local" v-model="s.dt" class="form-input w-full" />
						<Button
							variant="ghost"
							:disabled="sched.master.length === 1"
							@click="removeRow('master', i)"
						>
							<Trash2 class="size-4 text-ink-gray-6" />
						</Button>
					</div>
				</div>

				<Button variant="solid" :loading="saving === 'schedule'" @click="confirmSchedule">
					{{ __('Confirm Schedule') }}
				</Button>
			</div>

			<div
				v-else-if="!form.sessions_scheduled"
				class="mb-6 rounded-lg border bg-surface-gray-1 p-5 text-sm text-ink-gray-6"
			>
				{{ __('Feedback will open once the master trainer schedules the sessions.') }}
			</div>

			<!-- Feedback (after scheduling) -->
			<template v-if="form.sessions_scheduled">
				<!-- Manager sessions -->
				<template v-if="form.immediate_manager">
					<div class="mb-2 text-sm font-semibold text-ink-gray-7">{{ __('Manager Feedback') }}</div>
					<FeedbackBlock
						v-for="(s, i) in form.manager_sessions"
						:key="s.name"
						:title="`${__('Session')} ${i + 1}`"
						:recorded="!!s.recorded"
						:recorded-by="s.recorded_by"
						:recorded-on="s.recorded_on"
						:editable="form.can_edit_manager"
						:scheduled-datetime="s.meeting_datetime"
						:feedback="s.feedback"
						:saving="saving === `m:${s.name}`"
						@save="(p) => saveManager(s.name, p)"
					/>
				</template>

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
								<span class="font-medium text-ink-gray-8">{{ row.trainer_name || row.trainer }}</span>
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

				<!-- Master sessions -->
				<div class="mb-2 text-sm font-semibold text-ink-gray-7">
					{{ __('Master Trainer Feedback') }}
				</div>
				<FeedbackBlock
					v-for="(s, i) in form.master_sessions"
					:key="s.name"
					:title="`${__('Session')} ${i + 1}`"
					:recorded="!!s.recorded"
					:recorded-by="s.recorded_by"
					:recorded-on="s.recorded_on"
					:editable="form.can_edit_master"
					:scheduled-datetime="s.meeting_datetime"
					:feedback="s.feedback"
					:saving="saving === `x:${s.name}`"
					@save="(p) => saveMaster(s.name, p)"
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
					{{ __('All manager, trainer and master sessions must be recorded to complete.') }}
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
import { Plus, Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'frappe-ui'
import FeedbackBlock from '@/components/FeedbackBlock.vue'

const route = useRoute()
const feedbackName = route.params.name

const saving = ref(null)
const trainerFeedback = ref('')
const sched = reactive({ manager: [], master: [], trainers: {} })

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

const recordedTrainers = computed(() => form.value?.trainers.filter((t) => t.recorded).length || 0)

watch(form, (f) => {
	if (!f) return
	const myRow = f.trainers.find((t) => t.is_me)
	trainerFeedback.value = stripHtml(myRow?.feedback)

	sched.manager = f.manager_sessions.map((s) => ({ row: s.name, dt: toLocalInput(s.meeting_datetime) }))
	if (f.immediate_manager && !sched.manager.length) sched.manager = [{ row: null, dt: '' }]
	sched.master = f.master_sessions.map((s) => ({ row: s.name, dt: toLocalInput(s.meeting_datetime) }))
	if (!sched.master.length) sched.master = [{ row: null, dt: '' }]
	sched.trainers = {}
	for (const t of f.trainers) sched.trainers[t.name] = toLocalInput(t.meeting_datetime)
})

function addRow(which) {
	sched[which].push({ row: null, dt: '' })
}
function removeRow(which, i) {
	sched[which].splice(i, 1)
}

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
	const manager_times = sched.manager
		.filter((s) => s.dt)
		.map((s) => ({ row: s.row, meeting_datetime: toServer(s.dt) }))
	const master_times = sched.master
		.filter((s) => s.dt)
		.map((s) => ({ row: s.row, meeting_datetime: toServer(s.dt) }))
	const trainer_times = form.value.trainers.map((t) => ({
		row: t.name,
		meeting_datetime: toServer(sched.trainers[t.name]),
	}))
	return runAction(
		'schedule_sessions',
		{ name: feedbackName, manager_times, master_times, trainer_times },
		'schedule'
	)
}
function reschedule() {
	return runAction('reschedule_sessions', { name: feedbackName }, 'reschedule')
}
function saveManager(row, payload) {
	return runAction(
		'save_manager_feedback',
		{ name: feedbackName, feedback: payload.feedback, row },
		`m:${row}`
	)
}
function saveMaster(row, payload) {
	return runAction(
		'save_master_feedback',
		{ name: feedbackName, feedback: payload.feedback, row },
		`x:${row}`
	)
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
