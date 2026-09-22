<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'

interface DocumentItem {
  id: number
  title: string
  content: string | null
  file_path: string | null
  file_name: string | null
  visible_to_all: boolean
  visible_user_ids: number[]
  position: number
  created_by_id: number
  created_by_name: string
  created_at: string
  updated_at: string
}
interface UserOption {
  id: number
  full_name: string
  role: 'admin' | 'courier'
}

const { user } = useAuth()
const isAdmin = computed(() => user.value?.role === 'admin')

const documents = ref<DocumentItem[]>([])
const couriers = ref<UserOption[]>([])

const editingId = ref<number | null>(null)
const form = ref({ title: '', content: '', visible_to_all: true, visible_user_ids: [] as number[] })
const fileToUpload = ref<File | null>(null)
const submitting = ref(false)
const error = ref('')

const uploadingFileId = ref<number | null>(null)
const deletingId = ref<number | null>(null)

async function load() {
  documents.value = await api.get<DocumentItem[]>('/documents')
  if (isAdmin.value) {
    const all = await api.get<UserOption[]>('/auth/users')
    couriers.value = all.filter((u) => u.role === 'courier')
  }
}

function resetForm() {
  editingId.value = null
  form.value = { title: '', content: '', visible_to_all: true, visible_user_ids: [] }
  fileToUpload.value = null
  error.value = ''
}

function startEdit(doc: DocumentItem) {
  editingId.value = doc.id
  form.value = {
    title: doc.title,
    content: doc.content || '',
    visible_to_all: doc.visible_to_all,
    visible_user_ids: [...doc.visible_user_ids],
  }
  fileToUpload.value = null
  error.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function toggleVisibleUser(id: number) {
  const idx = form.value.visible_user_ids.indexOf(id)
  if (idx === -1) form.value.visible_user_ids.push(id)
  else form.value.visible_user_ids.splice(idx, 1)
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  fileToUpload.value = target.files?.[0] || null
}

async function submit() {
  error.value = ''
  if (!form.value.title.trim()) {
    error.value = 'Vyplň název.'
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      content: form.value.content.trim() || null,
      visible_to_all: form.value.visible_to_all,
      visible_user_ids: form.value.visible_to_all ? [] : form.value.visible_user_ids,
    }
    const doc = editingId.value
      ? await api.patch<DocumentItem>(`/documents/${editingId.value}`, payload)
      : await api.post<DocumentItem>('/documents', payload)

    if (fileToUpload.value) {
      const data = new FormData()
      data.set('file', fileToUpload.value)
      await api.post(`/documents/${doc.id}/file`, data)
    }

    resetForm()
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Nepodařilo se uložit'
  } finally {
    submitting.value = false
  }
}

async function replaceFile(doc: DocumentItem, e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  uploadingFileId.value = doc.id
  try {
    const data = new FormData()
    data.set('file', file)
    await api.post(`/documents/${doc.id}/file`, data)
    await load()
  } finally {
    uploadingFileId.value = null
    target.value = ''
  }
}

async function removeFile(doc: DocumentItem) {
  if (!window.confirm('Odebrat přiložený soubor z tohoto tutoriálu?')) return
  uploadingFileId.value = doc.id
  try {
    await api.delete(`/documents/${doc.id}/file`)
    await load()
  } finally {
    uploadingFileId.value = null
  }
}

async function remove(doc: DocumentItem) {
  if (!window.confirm(`Opravdu smazat "${doc.title}"?`)) return
  deletingId.value = doc.id
  try {
    await api.delete(`/documents/${doc.id}`)
    if (editingId.value === doc.id) resetForm()
    await load()
  } finally {
    deletingId.value = null
  }
}

function visibilityLabel(doc: DocumentItem) {
  if (doc.visible_to_all) return 'Vidí všichni'
  if (!doc.visible_user_ids.length) return 'Vidí jen admin'
  return `Vybraní (${doc.visible_user_ids.length})`
}

onMounted(load)
</script>

<template>
  <div>
    <h1><span class="eyebrow">Nápověda</span>Tutoriály</h1>

    <div class="card" v-if="isAdmin">
      <h3 style="margin-top:0">{{ editingId ? 'Upravit položku' : 'Nová položka' }}</h3>
      <form @submit.prevent="submit">
        <div class="field">
          <label>Název</label>
          <input v-model="form.title" required />
        </div>
        <div class="field">
          <label>Text tutoriálu (volitelné)</label>
          <textarea v-model="form.content" rows="6" placeholder="Návod, postup, poznámky…"></textarea>
        </div>
        <div class="field">
          <label>Příloha - dokument/soubor (volitelné)</label>
          <input type="file" @change="onFileChange" />
        </div>
        <div class="field">
          <label style="display:flex;align-items:center;gap:8px;font-weight:400">
            <input type="checkbox" style="width:auto" v-model="form.visible_to_all" />
            Vidí všichni kurýři
          </label>
        </div>
        <div class="field" v-if="!form.visible_to_all">
          <label>Kdo to uvidí</label>
          <p v-if="!couriers.length" style="font-size:13px;color:var(--muted);margin:0">
            Zatím nejsou žádní kurýři.
          </p>
          <div v-else style="display:flex;flex-wrap:wrap;gap:12px">
            <label
              v-for="c in couriers"
              :key="c.id"
              style="display:flex;align-items:center;gap:6px;font-weight:400;font-size:14px;width:auto;margin:0"
            >
              <input
                type="checkbox"
                style="width:auto"
                :checked="form.visible_user_ids.includes(c.id)"
                @change="toggleVisibleUser(c.id)"
              />
              {{ c.full_name }}
            </label>
          </div>
        </div>
        <div style="display:flex;gap:10px;align-items:center">
          <button class="btn" type="submit" :disabled="submitting">
            {{ submitting ? 'Ukládám…' : editingId ? 'Uložit změny' : 'Přidat' }}
          </button>
          <button v-if="editingId" class="btn secondary" type="button" @click="resetForm">Zrušit</button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
    </div>

    <div class="card" v-if="!documents.length">
      <p style="color:var(--muted);margin:0">Zatím tu nic není.</p>
    </div>

    <div class="card" v-for="doc in documents" :key="doc.id">
      <div style="display:flex;justify-content:space-between;align-items:start;gap:12px;flex-wrap:wrap">
        <h3 style="margin:0">{{ doc.title }}</h3>
        <span v-if="isAdmin" class="badge paid">{{ visibilityLabel(doc) }}</span>
      </div>
      <p v-if="doc.content" style="white-space:pre-wrap;margin:12px 0">{{ doc.content }}</p>

      <div v-if="doc.file_path" style="margin:12px 0">
        <a class="btn secondary" :href="`${api.API_URL}/${doc.file_path}`" target="_blank" rel="noopener">
          Stáhnout: {{ doc.file_name }}
        </a>
      </div>

      <div v-if="isAdmin" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
        <button class="btn secondary" type="button" @click="startEdit(doc)">Upravit</button>
        <label class="btn secondary" style="cursor:pointer">
          {{ doc.file_path ? 'Nahradit soubor' : 'Přidat soubor' }}
          <input
            type="file"
            style="display:none"
            :disabled="uploadingFileId === doc.id"
            @change="replaceFile(doc, $event)"
          />
        </label>
        <button v-if="doc.file_path" class="btn secondary" type="button" @click="removeFile(doc)">
          Odebrat soubor
        </button>
        <button
          class="btn secondary"
          type="button"
          style="color:var(--red)"
          :disabled="deletingId === doc.id"
          @click="remove(doc)"
        >
          {{ deletingId === doc.id ? 'Mažu…' : 'Smazat' }}
        </button>
      </div>
    </div>
  </div>
</template>
