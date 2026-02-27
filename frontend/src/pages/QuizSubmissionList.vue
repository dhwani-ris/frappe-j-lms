<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button
			v-if="submissions.data?.length"
			variant="solid"
			@click="showAnalytics = true"
		>
			<template #prefix>
				<BarChart3 class="size-4" />
			</template>
			{{ __('View Analytics') }}
		</Button>
	</header>
	<div v-if="submissions.data?.length" class="md:w-3/4 md:mx-auto py-5 mx-5">
		<div class="text-xl font-semibold mb-5 text-ink-gray-9">
			{{ submissions.data[0].quiz_title }}
		</div>
		<ListView
			:columns="quizColumns"
			:rows="submissions.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: false }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in quizColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'QuizSubmission',
						params: {
							submission: row.name,
						},
					}"
				>
					<ListRow :row="row" />
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="submissions.hasNextPage" @click="submissions.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<EmptyState v-else type="Quiz Submissions" />

	<!-- Quiz Analytics Modal -->
	<Dialog
		v-model="showAnalytics"
		:options="{
			title: __('Quiz Analytics'),
			size: '5xl',
		}"
	>
		<template #body-content>
			<div v-if="analytics.loading" class="flex items-center justify-center py-20">
				<LoadingIndicator class="size-8" />
			</div>
			<div v-else-if="analytics.data" class="space-y-6">
				<!-- Summary Cards -->
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<div class="border rounded-lg p-4">
						<div class="text-sm text-ink-gray-5">Total Attempts</div>
						<div class="text-2xl font-bold text-ink-gray-9 mt-1">
							{{ analytics.data.summary.total_attempts }}
						</div>
					</div>
					<div class="border rounded-lg p-4">
						<div class="text-sm text-ink-gray-5">Avg Score</div>
						<div class="text-2xl font-bold text-ink-gray-9 mt-1">
							{{ analytics.data.summary.avg_score }}%
						</div>
					</div>
					<div class="border rounded-lg p-4">
						<div class="text-sm text-ink-gray-5">Pass Rate</div>
						<div class="text-2xl font-bold text-green-600 mt-1">
							{{ analytics.data.summary.pass_rate }}%
						</div>
					</div>
					<div class="border rounded-lg p-4">
						<div class="text-sm text-ink-gray-5">Passed / Failed</div>
						<div class="text-2xl font-bold text-ink-gray-9 mt-1">
							{{ analytics.data.summary.passed }} / {{ analytics.data.summary.failed }}
						</div>
					</div>
				</div>

				<!-- Score Distribution -->
				<div class="border rounded-lg p-4">
					<div class="text-lg font-semibold mb-4">Score Distribution</div>
					<div class="grid grid-cols-5 gap-3">
						<div v-for="(count, range) in analytics.data.score_distribution" :key="range"
							class="text-center border rounded p-3">
							<div class="text-sm text-ink-gray-5">{{ range }}%</div>
							<div class="text-xl font-bold text-ink-gray-9 mt-1">{{ count }}</div>
						</div>
					</div>
				</div>

				<!-- Submissions Table -->
				<div class="border rounded-lg overflow-hidden">
					<div class="px-4 py-3 bg-surface-gray-1 border-b font-semibold">
						Recent Submissions
					</div>
					<table class="w-full">
						<thead>
							<tr class="border-b text-left text-sm text-ink-gray-5">
								<th class="px-4 py-3">Student</th>
								<th class="px-4 py-3">Score</th>
								<th class="px-4 py-3">Percentage</th>
								<th class="px-4 py-3">Status</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="sub in analytics.data.submissions.slice(0, 10)" :key="sub.name"
								class="border-b hover:bg-surface-gray-1">
								<td class="px-4 py-3 text-ink-gray-7">{{ sub.member_name }}</td>
								<td class="px-4 py-3 text-ink-gray-7">{{ sub.score }}</td>
								<td class="px-4 py-3 text-ink-gray-7">{{ sub.percentage }}%</td>
								<td class="px-4 py-3">
									<Badge
										:label="(sub.percentage >= 70) ? 'Passed' : 'Failed'"
										:theme="(sub.percentage >= 70) ? 'green' : 'red'"
									/>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	createListResource,
	createResource,
	Breadcrumbs,
	Button,
	Dialog,
	Badge,
	LoadingIndicator,
	ListView,
	ListRow,
	ListRows,
	ListHeader,
	ListHeaderItem,
	usePageMeta,
} from 'frappe-ui'
import { computed, onMounted, inject, ref, watch } from 'vue'
import { sessionStore } from '../stores/session'
import { useRouter } from 'vue-router'
import { BarChart3 } from 'lucide-vue-next'
import EmptyState from '@/components/EmptyState.vue'

const { brand } = sessionStore()
const router = useRouter()
const user = inject('$user')
const showAnalytics = ref(false)

onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator && !user.data?.is_trainer && !user.data?.is_master_trainer && !user.data?.is_lms_hr)
		router.push({ name: 'Courses' })
})

const props = defineProps({
	quizID: {
		type: String,
		required: true,
	},
})

const submissions = createListResource({
	doctype: 'LMS Quiz Submission',
	filters: {
		quiz: props.quizID,
	},
	fields: ['name', 'member_name', 'score', 'percentage', 'quiz_title'],
	orderBy: 'creation desc',
	auto: true,
})

const analytics = createResource({
	url: 'lms.lms.custom.dashboard_api.get_quiz_analytics',
	makeParams() {
		return {
			quiz_id: props.quizID,
		}
	},
	auto: false,
})

watch(showAnalytics, (newValue) => {
	if (newValue && !analytics.data) {
		analytics.fetch()
	}
})

const quizColumns = computed(() => {
	return [
		{
			label: __('Member'),
			key: 'member_name',
			width: 1,
		},
		{
			label: __('Score'),
			key: 'score',
			width: 1,
			align: 'center',
		},
		{
			label: __('Percentage'),
			key: 'percentage',
			width: 1,
			align: 'center',
		},
	]
})

const breadcrumbs = computed(() => {
	return [{ label: __('Quiz Submissions') }]
})

usePageMeta(() => {
	return {
		title: __('Quiz Submissions'),
		icon: brand.favicon,
	}
})
</script>
