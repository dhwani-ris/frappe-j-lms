<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Quiz Analytics - {0}', [employee?.employee_name || '']),
			size: '3xl',
		}"
	>
		<template #body-content>
			<div v-if="!employee" class="text-center py-10">
				<p class="text-ink-gray-5">{{ __('No data available') }}</p>
			</div>
			<div v-else>
				<!-- Summary Cards -->
				<div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
					<div class="border rounded-lg p-4 bg-surface-white">
						<div class="text-xs text-ink-gray-5">
							{{ __('Total Attempts') }}
						</div>
						<div class="text-2xl font-bold text-ink-gray-9 mt-1">
							{{ employee.quiz_scores?.length || 0 }}
						</div>
					</div>
					<div class="border rounded-lg p-4 bg-surface-white">
						<div class="text-xs text-ink-gray-5">{{ __('Average Score') }}</div>
						<div class="text-2xl font-bold text-blue-600 mt-1">
							{{ employee.avg_quiz_score || 0 }}%
						</div>
					</div>
					<div class="border rounded-lg p-4 bg-surface-white">
						<div class="text-xs text-ink-gray-5">{{ __('Highest Score') }}</div>
						<div class="text-2xl font-bold text-green-600 mt-1">
							{{ highestScore }}%
						</div>
					</div>
					<div class="border rounded-lg p-4 bg-surface-white">
						<div class="text-xs text-ink-gray-5">{{ __('Pass Rate') }}</div>
						<div class="text-2xl font-bold text-ink-gray-9 mt-1">
							{{ passRate }}%
						</div>
					</div>
				</div>

				<!-- Quiz Attempts Table -->
				<div class="border rounded-lg overflow-hidden">
					<div
						class="px-4 py-3 bg-surface-gray-1 border-b font-semibold text-ink-gray-9"
					>
						{{ __('Quiz Attempt History') }}
					</div>
					<div
						v-if="!employee.quiz_scores?.length"
						class="px-4 py-10 text-center text-ink-gray-5"
					>
						{{ __('No quiz attempts yet') }}
					</div>
					<table v-else class="w-full">
						<thead>
							<tr class="border-b text-left text-sm text-ink-gray-5">
								<th class="px-4 py-3">{{ __('Quiz') }}</th>
								<th v-if="hasCourseQuizzes" class="px-4 py-3 text-center">{{ __('Course') }}</th>
								<th v-if="hasResourceQuizzes" class="px-4 py-3 text-center">{{ __('Resource') }}</th>
								<th class="px-4 py-3 text-center">{{ __('Score') }}</th>
								<th class="px-4 py-3 text-center">{{ __('Percentage') }}</th>
								<th class="px-4 py-3 text-center">{{ __('Status') }}</th>
								<th class="px-4 py-3">{{ __('Attempted On') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="quiz in employee.quiz_scores"
								:key="quiz.name"
								class="border-b hover:bg-surface-gray-1"
							>
								<td class="px-4 py-3 text-ink-gray-9">
									{{ quiz.quiz_title || quiz.quiz }}
								</td>
								<td v-if="hasCourseQuizzes" class="px-4 py-3 text-center text-ink-gray-7">
									{{ quiz.context_type === 'course' ? quiz.context_label : '-' }}
								</td>
								<td v-if="hasResourceQuizzes" class="px-4 py-3 text-center text-ink-gray-7">
									{{ quiz.context_type === 'resource' ? quiz.context_label : '-' }}
								</td>
								<td class="px-4 py-3 text-center text-ink-gray-7">
									{{ quiz.score || 0 }}
								</td>
								<td class="px-4 py-3 text-center">
									<span
										class="font-semibold"
										:class="{
											'text-green-600': (quiz.percentage || 0) >= 70,
											'text-orange-600':
												(quiz.percentage || 0) >= 40 &&
												(quiz.percentage || 0) < 70,
											'text-red-600': (quiz.percentage || 0) < 40,
										}"
									>
										{{ quiz.percentage || 0 }}%
									</span>
								</td>
								<td class="px-4 py-3 text-center">
									<Badge
										:label="
											(quiz.percentage || 0) >= 70 ? __('Pass') : __('Fail')
										"
										:theme="(quiz.percentage || 0) >= 70 ? 'green' : 'red'"
										variant="subtle"
										size="sm"
									/>
								</td>
								<td class="px-4 py-3 text-sm text-ink-gray-5">
									{{ formatDate(quiz.creation) }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Score Distribution -->
				<div v-if="employee.quiz_scores?.length" class="mt-6">
					<div class="font-semibold text-ink-gray-9 mb-3">
						{{ __('Score Distribution') }}
					</div>
					<div class="grid grid-cols-5 gap-2">
						<div
							v-for="(range, index) in scoreRanges"
							:key="index"
							class="border rounded p-3 text-center"
						>
							<div class="text-xs text-ink-gray-5 mb-1">{{ range.label }}</div>
							<div class="text-lg font-semibold text-ink-gray-9">
								{{ range.count }}
							</div>
							<div class="text-xs text-ink-gray-5">{{ range.percentage }}%</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog, Badge } from 'frappe-ui'
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
	modelValue: Boolean,
	employee: Object,
})

const emit = defineEmits(['update:modelValue'])
const hasCourseQuizzes = computed(() =>
	props.employee?.quiz_scores?.some((q) => q.context_type === 'course')
)

const hasResourceQuizzes = computed(() =>
	props.employee?.quiz_scores?.some((q) => q.context_type === 'resource')
)

const show = computed({
	get: () => props.modelValue,
	set: (val) => emit('update:modelValue', val),
})

const formatDate = (date) => {
	return dayjs(date).format('DD MMM YYYY, HH:mm')
}

const highestScore = computed(() => {
	if (!props.employee?.quiz_scores?.length) return 0
	return Math.max(...props.employee.quiz_scores.map((q) => q.percentage || 0))
})

const passRate = computed(() => {
	if (!props.employee?.quiz_scores?.length) return 0
	const passed = props.employee.quiz_scores.filter(
		(q) => (q.percentage || 0) >= 70
	).length
	return Math.round((passed / props.employee.quiz_scores.length) * 100)
})

const scoreRanges = computed(() => {
	if (!props.employee?.quiz_scores?.length) return []

	const total = props.employee.quiz_scores.length
	const ranges = [
		{ label: '0-20%', min: 0, max: 20, count: 0 },
		{ label: '21-40%', min: 21, max: 40, count: 0 },
		{ label: '41-60%', min: 41, max: 60, count: 0 },
		{ label: '61-80%', min: 61, max: 80, count: 0 },
		{ label: '81-100%', min: 81, max: 100, count: 0 },
	]

	props.employee.quiz_scores.forEach((quiz) => {
		const percentage = quiz.percentage || 0
		const range = ranges.find((r) => percentage >= r.min && percentage <= r.max)
		if (range) range.count++
	})

	return ranges.map((r) => ({
		...r,
		percentage: total > 0 ? Math.round((r.count / total) * 100) : 0,
	}))
})
</script>
