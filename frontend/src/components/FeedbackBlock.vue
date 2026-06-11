<template>
	<div class="mb-6 rounded-lg border bg-surface-white p-5">
		<div class="mb-3 flex items-center justify-between">
			<div class="font-semibold text-ink-gray-9">{{ title }}</div>
			<Badge
				:theme="recorded ? 'green' : 'gray'"
				variant="subtle"
				:label="recorded ? __('Recorded') : __('Pending')"
			/>
		</div>

		<!-- Editable -->
		<div v-if="editable" class="space-y-2">
			<input type="datetime-local" v-model="localDatetime" class="form-input w-full" />
			<FormControl
				type="textarea"
				:rows="4"
				v-model="localFeedback"
				:placeholder="__('Meeting notes and feedback…')"
			/>
			<Button variant="solid" :loading="saving" @click="emitSave">
				{{ __('Save') }}
			</Button>
		</div>

		<!-- Read-only -->
		<div v-else>
			<div v-if="recordedBy" class="mb-2 text-xs text-ink-gray-5">
				{{ __('Recorded by') }} {{ recordedBy }}
				<span v-if="recordedOn"> · {{ recordedOn }}</span>
			</div>
			<div
				v-if="feedback"
				class="prose prose-sm max-w-none text-ink-gray-7"
				v-html="feedback"
			/>
			<div v-else class="text-sm text-ink-gray-4">{{ __('Not recorded yet.') }}</div>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, FormControl } from 'frappe-ui'
import { ref, watch } from 'vue'

const props = defineProps({
	title: String,
	recorded: Boolean,
	recordedBy: String,
	recordedOn: String,
	editable: Boolean,
	datetime: String,
	feedback: String,
	saving: Boolean,
})
const emit = defineEmits(['save'])

const localDatetime = ref(props.datetime || '')
const localFeedback = ref(stripHtml(props.feedback))

watch(
	() => props.datetime,
	(v) => (localDatetime.value = v || '')
)
watch(
	() => props.feedback,
	(v) => (localFeedback.value = stripHtml(v))
)

function stripHtml(html) {
	if (!html) return ''
	const tmp = document.createElement('div')
	tmp.innerHTML = html
	return (tmp.textContent || tmp.innerText || '').trim()
}

function emitSave() {
	emit('save', { datetime: localDatetime.value, feedback: localFeedback.value })
}
</script>
