<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div class="flex items-center space-x-2">
			<div class="flex items-center rounded-md border overflow-hidden">
				<button
					type="button"
					class="p-1.5"
					:class="
						viewMode === 'grid'
							? 'bg-surface-gray-2 text-ink-gray-9'
							: 'text-ink-gray-5 hover:bg-surface-gray-1'
					"
					:aria-label="__('Grid view')"
					@click="viewMode = 'grid'"
				>
					<LayoutGrid class="h-4 w-4 stroke-1.5" />
				</button>
				<button
					type="button"
					class="p-1.5"
					:class="
						viewMode === 'list'
							? 'bg-surface-gray-2 text-ink-gray-9'
							: 'text-ink-gray-5 hover:bg-surface-gray-1'
					"
					:aria-label="__('List view')"
					@click="viewMode = 'list'"
				>
					<List class="h-4 w-4 stroke-1.5" />
				</button>
			</div>
			<FileUploader
				v-if="canManage"
				:uploadArgs="{ folder: currentFolder, private: true }"
				@success="onUploadSuccess"
				@failure="onUploadFailure"
			>
				<template #default="{ openFileSelector, uploading, progress }">
					<Dropdown
						:options="[
							{
								label: __('Upload File'),
								icon: Upload,
								onClick: openFileSelector,
							},
							{
								label: __('New Folder'),
								icon: FolderPlus,
								onClick: () => (showNewFolder = true),
							},
						]"
					>
						<template v-slot="{ open }">
							<Button variant="solid" :loading="uploading">
								<template #prefix>
									<Upload class="h-4 w-4 stroke-1.5" />
								</template>
								{{
									uploading ? `${__('Uploading')} ${progress}%` : __('Upload')
								}}
							</Button>
						</template>
					</Dropdown>
				</template>
			</FileUploader>
		</div>
	</header>

	<div class="px-5 pt-4 sm:px-10">
		<FormControl
			type="text"
			v-model="searchQuery"
			:placeholder="__('Search resources by name...')"
			class="max-w-sm"
		>
			<template #prefix>
				<Search class="h-4 w-4 stroke-1.5 text-ink-gray-5" />
			</template>
		</FormControl>
	</div>

	<div class="px-5 py-5 sm:px-10">
		<EmptyState
			v-if="!loading && !isSearching && items.length === 0"
			type="Resources"
		/>
		<div
			v-else-if="!loading && isSearching && items.length === 0"
			class="text-ink-gray-5 text-center py-10"
		>
			{{ __('No results for "{0}"').format(searchQuery) }}
		</div>

		<div
			v-else-if="viewMode === 'grid'"
			class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4"
		>
			<div
				v-for="item in items"
				:key="item.name"
				class="group relative border rounded-lg p-4 hover:bg-surface-gray-1 hover:shadow-sm transition-all cursor-pointer"
				@click="item.is_folder ? openFolder(item.name) : viewFile(item)"
			>
				<div
					v-if="tileActions(item).length"
					class="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
					@click.stop
				>
					<Dropdown :options="tileActions(item)">
						<template v-slot="{ open }">
							<Button variant="ghost" size="sm">
								<MoreVertical class="h-4 w-4 stroke-1.5" />
							</Button>
						</template>
					</Dropdown>
				</div>
				<div class="flex flex-col items-center text-center space-y-2">
					<component
						:is="tileIcon(item)"
						class="h-10 w-10 stroke-1 shrink-0"
						:class="item.is_folder ? 'text-ink-gray-9' : 'text-ink-gray-6'"
					/>
					<div class="w-full min-w-0">
						<div
							class="truncate text-sm font-medium text-ink-gray-8"
							:title="item.file_name"
						>
							{{ item.file_name }}
						</div>
						<div
							v-if="isSearching"
							class="text-xs text-ink-gray-5 truncate cursor-pointer hover:underline"
							@click.stop="jumpToFolder(item)"
						>
							{{ __('in {0}').format(item.folder_label) }}
						</div>
						<div class="flex flex-wrap items-center justify-center gap-1 mt-1">
							<Badge
								v-if="getBadge(item)"
								:theme="getBadge(item).theme"
								size="sm"
							>
								{{ getBadge(item).label }}
							</Badge>
							<Badge
								v-if="!item.is_folder && !item.can_download"
								theme="orange"
								size="sm"
							>
								{{ __('View Only') }}
							</Badge>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div v-else class="divide-y border rounded-lg">
			<div
				v-for="item in items"
				:key="item.name"
				class="flex items-center justify-between px-4 py-3 hover:bg-surface-gray-1"
			>
				<div
					class="flex items-center space-x-3 flex-1 min-w-0"
					:class="item.is_folder ? 'cursor-pointer' : ''"
					@click="item.is_folder ? openFolder(item.name) : null"
				>
					<Folder
						v-if="item.is_folder"
						class="h-5 w-5 stroke-1.5 text-ink-gray-6 shrink-0"
					/>
					<FileText
						v-else
						class="h-5 w-5 stroke-1.5 text-ink-gray-6 shrink-0"
					/>
					<div class="min-w-0">
						<div class="flex items-center space-x-2">
							<div class="truncate font-medium text-ink-gray-8">
								{{ item.file_name }}
							</div>
							<Badge
								v-if="canManage && !item.is_live && !item.published"
								theme="gray"
							>
								{{ __('Draft') }}
							</Badge>
							<Badge
								v-else-if="
									canManage &&
									!item.is_live &&
									item.published &&
									isFutureDate(item.publish_on)
								"
								theme="blue"
							>
								{{ __('Scheduled for {0}').format(item.publish_on) }}
							</Badge>
							<Badge
								v-else-if="canManage && !item.is_live && item.published"
								theme="gray"
							>
								{{ __('Hidden (folder not published)') }}
							</Badge>
							<Badge v-else-if="canManage && item.is_live" theme="green">
								{{ __('Live') }}
							</Badge>
						</div>
						<div v-if="isSearching" class="text-sm text-ink-gray-5">
							<span
								class="cursor-pointer hover:underline"
								@click.stop="jumpToFolder(item)"
							>
								{{ __('in {0}').format(item.folder_label) }}
							</span>
						</div>
						<div
							v-if="!item.is_folder"
							class="text-sm text-ink-gray-5 flex items-center space-x-2"
						>
							<span v-if="item.quiz">
								{{ __('Quiz:') }} {{ item.quiz.title }}
							</span>
							<Badge v-if="!item.can_download" theme="orange">
								{{ __('View Only') }}
							</Badge>
						</div>
					</div>
				</div>

				<div
					v-if="!item.is_folder"
					class="flex items-center space-x-2 shrink-0"
				>
					<Button size="sm" @click="viewFile(item)">
						{{ item.viewed ? __('View Again') : __('View') }}
					</Button>
					<Button
						v-if="item.can_download"
						size="sm"
						@click="downloadFile(item)"
					>
						<template #prefix>
							<Download class="h-4 w-4 stroke-1.5" />
						</template>
						{{ __('Download') }}
					</Button>
					<router-link
						v-if="item.quiz && item.viewed"
						:to="{ name: 'QuizPage', params: { quizID: item.quiz.name } }"
					>
						<Button size="sm" variant="solid">
							<template #prefix>
								<ListChecks class="h-4 w-4 stroke-1.5" />
							</template>
							{{ __('Take Quiz') }}
						</Button>
					</router-link>
					<Button
						v-else-if="item.quiz"
						size="sm"
						disabled
						:title="
							__('View or download the document first to unlock this quiz')
						"
					>
						<template #prefix>
							<ListChecks class="h-4 w-4 stroke-1.5" />
						</template>
						{{ __('View document to unlock quiz') }}
					</Button>
				</div>

				<div v-if="canManage" class="flex items-center space-x-2 shrink-0 ml-2">
					<Button size="sm" @click="openManageDialog(item)">
						<template #prefix>
							<Settings class="h-4 w-4 stroke-1.5" />
						</template>
						{{ __('Manage') }}
					</Button>
					<Button
						v-if="!item.is_folder"
						size="sm"
						@click="openReplaceDialog(item)"
					>
						<template #prefix>
							<RefreshCw class="h-4 w-4 stroke-1.5" />
						</template>
						{{ __('Replace') }}
					</Button>
					<Button size="sm" theme="red" @click="confirmDelete(item)">
						<Trash2 class="h-4 w-4 stroke-1.5" />
					</Button>
				</div>
			</div>
		</div>
	</div>

	<Dialog
		v-model="showManageDialog"
		:options="{
			title: manageTarget
				? __('Manage {0}').format(manageTarget.file_name)
				: '',
			size: 'sm',
		}"
	>
		<template #body-content>
			<div v-if="manageTarget" class="space-y-4">
				<FormControl
					type="checkbox"
					:modelValue="Boolean(manageTarget.published)"
					:label="__('Published')"
					@update:modelValue="(value) => setPublished(manageTarget, value)"
				/>
				<FormControl
					v-if="manageTarget.published"
					type="date"
					:modelValue="manageTarget.publish_on || ''"
					:label="__('Publish On')"
					:placeholder="__('Immediately')"
					@update:modelValue="(value) => setPublishOn(manageTarget, value)"
				/>
				<FormControl
					v-if="manageTarget.is_folder"
					type="select"
					:modelValue="manageTarget.download_permission || ''"
					:label="__('Download Permission')"
					:options="[
						{ label: __('View & Download'), value: 'View & Download' },
						{ label: __('View Only'), value: 'View Only' },
					]"
					@update:modelValue="
						(value) => setFolderPermission(manageTarget, value)
					"
				/>
			</div>
		</template>
	</Dialog>

	<Dialog
		v-model="showNewFolder"
		:options="{
			title: __('Create Folder'),
			size: 'sm',
			actions: [
				{
					label: __('Create'),
					variant: 'solid',
					onClick: createFolder,
				},
			],
		}"
	>
		<template #body-content>
			<FormControl
				v-model="newFolderName"
				:label="__('Folder Name')"
				type="text"
				@keydown.enter="createFolder"
			/>
		</template>
	</Dialog>

	<Dialog
		v-model="showDeleteConfirm"
		:options="{
			title: __('Delete'),
			message: __(
				'Are you sure you want to delete {0}? This cannot be undone.'
			).format(deleteTarget?.file_name),
			size: 'sm',
			actions: [
				{
					label: __('Delete'),
					variant: 'solid',
					theme: 'red',
					onClick: deleteConfirmed,
				},
			],
		}"
	/>

	<input
		ref="replaceInput"
		type="file"
		class="hidden"
		@change="onReplaceFileChosen"
	/>

	<Dialog
		v-model="showViewer"
		:options="{
			title: viewingItem?.file_name,
			size: '5xl',
		}"
	>
		<template #body-content>
			<iframe
				v-if="viewingItem"
				:src="`${streamUrl(viewingItem, false)}#toolbar=0`"
				class="w-full border rounded-lg"
				style="height: 75vh"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	Dialog,
	Dropdown,
	FileUploader,
	FormControl,
	call,
	toast,
} from 'frappe-ui'
import EmptyState from '@/components/EmptyState.vue'
import {
	Download,
	File as FileIcon,
	FileSpreadsheet,
	FileText,
	Folder,
	FolderPlus,
	Image as ImageIcon,
	LayoutGrid,
	List,
	ListChecks,
	MoreVertical,
	Presentation,
	RefreshCw,
	Search,
	Settings,
	Trash2,
	Upload,
} from 'lucide-vue-next'

const ROOT_FOLDER = 'Home/LMS Resources'

// PDF renders inline natively; PPT/PPTX get converted to PDF server-side
// (stream_resource, via headless LibreOffice) before being streamed back,
// so they can go through the exact same inline viewer.
const INLINE_VIEWABLE_TYPES = ['PDF', 'PPT', 'PPTX']

const props = defineProps({
	folder: {
		type: String,
		default: null,
	},
})

const router = useRouter()
const user = inject('$user')

const currentFolder = computed(() =>
	props.folder ? decodeURIComponent(props.folder) : ROOT_FOLDER
)

const items = ref([])
const loading = ref(false)
const viewMode = ref('grid')
const searchQuery = ref('')
const isSearching = computed(() => searchQuery.value.trim().length > 0)
let searchDebounceTimer = null

const canManage = computed(() => {
	const data = user?.data
	return Boolean(
		data && (data.is_moderator || data.is_instructor || data.is_master_trainer)
	)
})

const loadContents = async () => {
	loading.value = true
	try {
		items.value = await call(
			'lms.lms.custom.resource_api.get_folder_contents',
			{
				folder: currentFolder.value,
			}
		)
	} catch (err) {
		toast.error(
			__('Failed to load Resources: ') +
				(err.messages?.[0] || err.message || err)
		)
	} finally {
		loading.value = false
	}
}

const runSearch = async () => {
	loading.value = true
	try {
		items.value = await call('lms.lms.custom.resource_api.search_resources', {
			query: searchQuery.value.trim(),
		})
	} catch (err) {
		toast.error(
			__('Search failed: ') + (err.messages?.[0] || err.message || err)
		)
	} finally {
		loading.value = false
	}
}

onMounted(loadContents)
watch(currentFolder, () => {
	// Navigating via the folder tree always means "browse," not "search" -
	// otherwise landing on a new folder while an old query is still in
	// the box would confusingly keep showing search results instead of
	// that folder's actual contents.
	searchQuery.value = ''
	loadContents()
})

// Debounced so every keystroke doesn't fire a request - searches
// everywhere under Resources, not just the current folder (see
// decision.md - a search that only works if you're already in the
// right folder isn't solving the actual problem).
watch(searchQuery, () => {
	clearTimeout(searchDebounceTimer)
	searchDebounceTimer = setTimeout(() => {
		if (isSearching.value) {
			runSearch()
		} else {
			loadContents()
		}
	}, 300)
})

const jumpToFolder = (item) => {
	searchQuery.value = ''
	openFolder(item.folder)
}

const breadcrumbs = computed(() => {
	const segments = currentFolder.value.split('/').filter(Boolean)
	// segments[0] is always "Home" - the root of Frappe's file tree, not
	// meaningful to a user browsing Resources, so it's hidden and the
	// second segment ("LMS Resources") becomes the visible root instead.
	const crumbs = [{ label: __('Resources'), route: { name: 'Resources' } }]
	let pathSoFar = segments[0]
	for (let i = 1; i < segments.length; i++) {
		pathSoFar += '/' + segments[i]
		crumbs.push({
			label: segments[i],
			route: {
				name: 'Resources',
				params: { folder: encodeURIComponent(pathSoFar) },
			},
		})
	}
	return crumbs
})

const openFolder = (folderName) => {
	router.push({
		name: 'Resources',
		params: { folder: encodeURIComponent(folderName) },
	})
}

const onUploadSuccess = () => {
	toast.success(__('Document uploaded'))
	loadContents()
}

const onUploadFailure = (err) => {
	console.error('Resource upload failed:', err)
	toast.error(
		__('Upload failed: ') + (err?.messages?.[0] || err?.message || err)
	)
}

const showNewFolder = ref(false)
const newFolderName = ref('')

const createFolder = async ({ close } = {}) => {
	if (!newFolderName.value.trim()) return
	try {
		await call('lms.lms.custom.resource_api.create_resource_folder', {
			folder: currentFolder.value,
			file_name: newFolderName.value.trim(),
		})
		toast.success(__('Folder created'))
		newFolderName.value = ''
		showNewFolder.value = false
		close?.()
		loadContents()
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || err)
	}
}

// Used only to decide the badge wording (Scheduled vs. Hidden) - a
// publish_on that's already in the past means the file's own schedule
// has already arrived and it's now some ancestor folder blocking
// visibility instead, which is a different, more accurate thing to tell
// an admin than "still scheduled for [a date that's already gone by]".
const isFutureDate = (dateStr) => {
	if (!dateStr) return false
	return new Date(dateStr) > new Date()
}

// Grid-view only - the list view's existing badge markup is left exactly
// as it was (same v-if/v-else-if chain, just written inline there) to
// avoid touching working UI; this mirrors that same precedence for the
// new tile layout instead of duplicating the chain a second time.
const getBadge = (item) => {
	if (canManage.value && !item.is_live && !item.published) {
		return { theme: 'gray', label: __('Draft') }
	}
	if (
		canManage.value &&
		!item.is_live &&
		item.published &&
		isFutureDate(item.publish_on)
	) {
		return {
			theme: 'blue',
			label: __('Scheduled for {0}').format(item.publish_on),
		}
	}
	if (canManage.value && !item.is_live && item.published) {
		return { theme: 'gray', label: __('Hidden (folder not published)') }
	}
	if (canManage.value && item.is_live) {
		return { theme: 'green', label: __('Live') }
	}
	return null
}

const tileIcon = (item) => {
	if (item.is_folder) return Folder
	const type = (item.file_type || '').toUpperCase()
	if (['JPG', 'JPEG', 'PNG', 'GIF', 'SVG', 'WEBP'].includes(type))
		return ImageIcon
	if (['PPT', 'PPTX'].includes(type)) return Presentation
	if (['XLS', 'XLSX', 'CSV'].includes(type)) return FileSpreadsheet
	if (type === 'PDF') return FileText
	return FileIcon
}

// Everything a tile's kebab menu can do - the same actions the list
// view's row buttons already expose, just collected into one dropdown
// since a tile has no room for 5+ separate buttons. Clicking the tile
// itself (see the grid markup) already handles View/Open, so that's
// deliberately not repeated here.
const tileActions = (item) => {
	const actions = []
	if (!item.is_folder) {
		if (item.can_download) {
			actions.push({
				label: __('Download'),
				icon: Download,
				onClick: () => downloadFile(item),
			})
		}
		if (item.quiz && item.viewed) {
			actions.push({
				label: __('Take Quiz'),
				icon: ListChecks,
				onClick: () =>
					router.push({ name: 'QuizPage', params: { quizID: item.quiz.name } }),
			})
		}
	}
	if (canManage.value) {
		actions.push({
			label: __('Manage'),
			icon: Settings,
			onClick: () => openManageDialog(item),
		})
		if (!item.is_folder) {
			actions.push({
				label: __('Replace'),
				icon: RefreshCw,
				onClick: () => openReplaceDialog(item),
			})
		}
		actions.push({
			label: __('Delete'),
			icon: Trash2,
			onClick: () => confirmDelete(item),
		})
	}
	return actions
}

const showManageDialog = ref(false)
const manageTarget = ref(null)

const openManageDialog = (item) => {
	manageTarget.value = item
	showManageDialog.value = true
}

const setFolderPermission = async (item, value) => {
	try {
		await call('lms.lms.custom.resource_api.set_resource_download_permission', {
			file_name: item.name,
			value,
		})
		item.download_permission = value
		toast.success(__('Updated'))
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || err)
	}
}

const setPublished = async (item, value) => {
	try {
		await call('lms.lms.custom.resource_api.set_resource_published', {
			file_name: item.name,
			value: value ? 1 : 0,
		})
		item.published = value
		toast.success(value ? __('Published') : __('Unpublished'))
		// Deliberately not reloading the whole list here: it would replace
		// every item with a fresh object, silently disconnecting the open
		// Manage dialog's `manageTarget` reference from the row underneath
		// it. The direct mutation above already updates this item's own
		// badge/state immediately; other rows (e.g. children of a folder
		// just published) will pick up the new state on next navigation.
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || err)
	}
}

const setPublishOn = async (item, value) => {
	try {
		await call('lms.lms.custom.resource_api.set_resource_publish_on', {
			file_name: item.name,
			value,
		})
		item.publish_on = value
		toast.success(value ? __('Scheduled') : __('Publishing immediately'))
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || err)
	}
}

const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

const confirmDelete = (item) => {
	deleteTarget.value = item
	showDeleteConfirm.value = true
}

const deleteConfirmed = async ({ close } = {}) => {
	try {
		await call('lms.lms.custom.resource_api.delete_resource', {
			file_name: deleteTarget.value.name,
		})
		toast.success(__('Deleted'))
		showDeleteConfirm.value = false
		close?.()
		loadContents()
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || err)
	}
}

const replaceInput = ref(null)
const replaceTarget = ref(null)

const openReplaceDialog = (item) => {
	replaceTarget.value = item
	replaceInput.value?.click()
}

const onReplaceFileChosen = async (e) => {
	const file = e.target.files[0]
	e.target.value = ''
	if (!file || !replaceTarget.value) return

	const formData = new FormData()
	formData.append('file', file)
	formData.append('file_name', replaceTarget.value.name)

	try {
		const response = await fetch(
			'/api/method/lms.lms.custom.resource_api.replace_resource_file',
			{
				method: 'POST',
				headers: {
					'X-Frappe-CSRF-Token': window.csrf_token || window.frappe?.csrf_token,
				},
				body: formData,
			}
		)
		if (!response.ok) {
			const err = await response.json()
			throw new Error(err.exception || err.message || __('Replace failed'))
		}
		toast.success(__('Document replaced'))
		loadContents()
	} catch (err) {
		toast.error(err.message || __('Replace failed'))
	}
}

// Both "View" and "Download" hit frappe.client.get first so Frappe's
// built-in View Log (enabled on File via a Property Setter) records the
// access - this is what a resource-gated quiz checks before allowing an
// attempt. See flow.md, sections 5-7.
// Explicit, rather than relying on Frappe's own View Log auto-logging -
// that only fires from the Desk UI's own document-open endpoint
// (frappe.desk.form.load.getdoc), never from a generic API call like
// frappe.client.get. See resource_api.py's mark_resource_viewed docstring.
const registerView = (item) =>
	call('lms.lms.custom.resource_api.mark_resource_viewed', {
		file_name: item.name,
	})

// Never point the browser at item.file_url directly - Frappe's native
// private-file route checks permission via a plain function call that
// bypasses the has_permission hooks pipeline (see resource_api.py's
// stream_resource docstring), so it hard-denies every non-admin user
// regardless of our own rules. Everything goes through our own
// whitelisted endpoint instead, which checks frappe.has_permission()
// (hook-aware) before returning any bytes.
const streamUrl = (item, asAttachment) =>
	`/api/method/lms.lms.custom.resource_api.stream_resource?file_name=${encodeURIComponent(
		item.name
	)}&as_attachment=${asAttachment ? 1 : 0}`

const showViewer = ref(false)
const viewingItem = ref(null)

const viewFile = async (item) => {
	try {
		await registerView(item)
		item.viewed = true
	} catch (err) {
		toast.error(
			__('Unable to open this document: ') +
				(err?.messages?.[0] || err?.message || err)
		)
		return
	}
	if (INLINE_VIEWABLE_TYPES.includes(item.file_type)) {
		// Embedded in our own page with the browser's PDF toolbar hidden
		// (#toolbar=0) so there's no built-in download button to click -
		// same trick this app already uses for lesson PDFs (lms/plugins.py
		// pdf_renderer). Opening a bare new tab instead would hand the
		// user the browser's own PDF viewer, download button included.
		// PPT/PPTX get converted to PDF server-side first (stream_resource,
		// via headless LibreOffice) - to this iframe it's just a PDF
		// either way.
		viewingItem.value = item
		showViewer.value = true
	} else {
		// Any other type has no way to render inline in a browser at all,
		// so there's no toolbar to hide - falls back to a plain new tab.
		window.open(streamUrl(item, false), '_blank')
	}
}

const downloadFile = async (item) => {
	try {
		await registerView(item)
		item.viewed = true
	} catch (err) {
		toast.error(
			__('Unable to download this document: ') +
				(err?.messages?.[0] || err?.message || err)
		)
		return
	}
	window.open(streamUrl(item, true), '_blank')
}
</script>
