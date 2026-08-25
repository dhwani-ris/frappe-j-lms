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
				]"
			/>
		</header>

		<div class="p-5">
			<EmployeeFeedbackList
				:heading="__('Employee Feedback')"
				:show-empty="true"
				:show-filters="true"
			/>
		</div>
	</div>
</template>

<script setup>
import { Breadcrumbs } from 'frappe-ui'
import EmployeeFeedbackList from '@/components/EmployeeFeedbackList.vue'
</script>
