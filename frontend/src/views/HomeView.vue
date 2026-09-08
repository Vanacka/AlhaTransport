<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/client'
import { useAuth } from '../stores/auth'

interface HomeTask {
  id: number
  user_id: number
  date: string
  text: string
  done: boolean
}

interface Checklist {
  date: string
  car_checked: boolean
  refueled: boolean
  form_filled: boolean
  is_day_off: boolean
  day_off_reason: 'weekend' | 'holiday' | 'vacation' | null
  holiday_name: string | null
  extra_tasks: HomeTask[]
}

interface UserOption { id: number; full_name: string; role: 'admin' | 'courier' }

const { user } = useAuth()
const isAdmin = computed(() => user.value?.role === 'admin')

const checklist = ref<Checklist | null>(null)
const savingField = ref<'car_checked' | 'refueled' | null>(null)
const togglingTaskId = ref<number | null>(null)

const todayLabel = computed(() =>
  new Date().toLocaleDateString('cs-CZ', { weekday: 'long', day: 'numeric', month: 'long' }),
)

const dayOffTitle = computed(() => {
  if (checklist.value?.day_off_reason === 'weekend') return 'Dnes je víkend'
  if (checklist.value?.day_off_reason === 'holiday') return 'Dnes je státní svátek'
  return 'Dnes máš dovolenou'
})

const doneCount = computed(() => {
  if (!checklist.value) return 0
  return [checklist.value.car_checked, checklist.value.refueled, checklist.value.form_filled].filter(
    Boolean,
  ).length
})

async function load() {
  checklist.value = await api.get<Checklist>('/checklist/today')
}

async function toggle(field: 'car_checked' | 'refueled') {
  if (!checklist.value || savingField.value) return
  const next = !checklist.value[field]
  checklist.value[field] = next
  savingField.value = field
  try {
    checklist.value = await api.patch<Checklist>('/checklist/today', { [field]: next })
  } catch {
    checklist.value[field] = !next
  } finally {
    savingField.value = null
  }
}

async function toggleTask(task: HomeTask) {
  if (togglingTaskId.value) return
  const next = !task.done
  task.done = next
  togglingTaskId.value = task.id
  try {
    await api.patch<HomeTask>(`/checklist/tasks/${task.id}`, { done: next })
  } catch {
    task.done = !next
  } finally {
    togglingTaskId.value = null
  }
}

// ---------- Admin: přidávání a správa úkolů navíc ----------

const allUsers = ref<UserOption[]>([])
const couriers = computed(() => allUsers.value.filter((u) => u.role === 'courier'))
const upcomingTasks = ref<HomeTask[]>([])

const newTask = ref({ text: '', date: new Date().toISOString().slice(0, 10), user_ids: [] as number[] })
const allSelected = computed({
  get: () => couriers.value.length > 0 && newTask.value.user_ids.length === couriers.value.length,
  set: (val: boolean) => {
    newTask.value.user_ids = val ? couriers.value.map((c) => c.id) : []
  },
})
const taskSubmitting = ref(false)
const taskError = ref('')
const deletingTaskId = ref<number | null>(null)

function courierName(userId: number) {
  return allUsers.value.find((u) => u.id === userId)?.full_name || `#${userId}`
}

async function loadAdminData() {
  if (!isAdmin.value) return
  const [users, tasks] = await Promise.all([
    api.get<UserOption[]>('/auth/users'),
    api.get<HomeTask[]>('/checklist/tasks'),
  ])
  allUsers.value = users
  upcomingTasks.value = tasks
}

async function submitTask() {
  taskError.value = ''
  if (!newTask.value.text.trim()) {
    taskError.value = 'Napiš text úkolu'
    return
  }
  if (!newTask.value.user_ids.length) {
    taskError.value = 'Vyber aspoň jednoho kurýra'
    return
  }
  taskSubmitting.value = true
  try {
    await api.post('/checklist/tasks', newTask.value)
    newTask.value = { text: '', date: new Date().toISOString().slice(0, 10), user_ids: [] }
    await loadAdminData()
    await load()
  } catch (e) {
    taskError.value = e instanceof Error ? e.message : 'Nepodařilo se přidat úkol'
  } finally {
    taskSubmitting.value = false
  }
}

async function deleteTask(task: HomeTask) {
  deletingTaskId.value = task.id
  try {
    await api.delete(`/checklist/tasks/${task.id}`)
    upcomingTasks.value = upcomingTasks.value.filter((t) => t.id !== task.id)
    await load()
  } finally {
    deletingTaskId.value = null
  }
}

onMounted(async () => {
  await Promise.all([load(), loadAdminData()])
})
</script>

<template>
  <div>
    <h1><span class="eyebrow">Dnešní směna</span>Ahoj, {{ user?.full_name }}</h1>
    <p class="today-date">{{ todayLabel }}</p>

    <div class="card vacation-card" v-if="checklist?.is_day_off">
      <h3 style="margin-top: 0">{{ dayOffTitle }}{{ checklist.holiday_name ? ` (${checklist.holiday_name})` : '' }}</h3>
      <p style="margin: 0; color: var(--muted)">Žádné úkoly na dnešek nemáš, užij si volno.</p>
    </div>

    <div class="card checklist-card" v-else-if="checklist">
      <div class="checklist-header">
        <h3>Úkoly na dnešní den</h3>
        <span class="checklist-progress">{{ doneCount }}/3 hotovo</span>
      </div>

      <ul class="checklist">
        <li class="checklist-item" :class="{ done: checklist.car_checked }">
          <button
            type="button"
            class="check-toggle"
            :disabled="savingField === 'car_checked'"
            @click="toggle('car_checked')"
          >
            <span class="check-box" :class="{ checked: checklist.car_checked }"></span>
            <span class="check-label">Zkontrolovat auto</span>
          </button>
        </li>

        <li class="checklist-item" :class="{ done: checklist.refueled }">
          <button
            type="button"
            class="check-toggle"
            :disabled="savingField === 'refueled'"
            @click="toggle('refueled')"
          >
            <span class="check-box" :class="{ checked: checklist.refueled }"></span>
            <span class="check-label">Natankovat</span>
          </button>
        </li>

        <li class="checklist-item" :class="{ done: checklist.form_filled }">
          <router-link to="/vykon" class="check-toggle">
            <span class="check-box" :class="{ checked: checklist.form_filled }"></span>
            <span class="check-label">
              Vyplnit formulář trasy
              <span class="check-hint">
                {{
                  checklist.form_filled
                    ? 'Dnes už vyplněno'
                    : 'Odškrtne se, až formulář výkonu vyplníš celý bez přeskočení'
                }}
              </span>
            </span>
          </router-link>
        </li>
      </ul>
    </div>

    <div class="card" v-else>Načítám úkoly…</div>

    <div class="card checklist-card" v-if="checklist?.extra_tasks?.length">
      <h3 style="margin-top:0">Úkoly navíc na dnešek</h3>
      <ul class="checklist">
        <li v-for="t in checklist.extra_tasks" :key="t.id" class="checklist-item" :class="{ done: t.done }">
          <button
            type="button"
            class="check-toggle"
            :disabled="togglingTaskId === t.id"
            @click="toggleTask(t)"
          >
            <span class="check-box" :class="{ checked: t.done }"></span>
            <span class="check-label">{{ t.text }}</span>
          </button>
        </li>
      </ul>
    </div>

    <div class="card" v-if="isAdmin">
      <h3 style="margin-top:0">Přidat úkol kurýrům</h3>
      <p style="font-size:12px;color:var(--muted);margin-top:-8px">
        Úkol se kurýrovi objeví na hlavní stránce ve zvolený den - i o víkendu, svátku nebo dovolené.
      </p>
      <form @submit.prevent="submitTask">
        <div class="form-row">
          <div class="field" style="flex:1;min-width:220px">
            <label>Text úkolu</label>
            <input v-model="newTask.text" placeholder="např. Vyzvedni si výplatu" />
          </div>
          <div class="field">
            <label>Den</label>
            <input v-model="newTask.date" type="date" />
          </div>
        </div>
        <div class="field">
          <label style="display:flex;align-items:center;gap:6px">
            <input type="checkbox" v-model="allSelected" style="width:auto" />
            Vybrat všechny kurýry
          </label>
          <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:6px">
            <label v-for="c in couriers" :key="c.id" style="display:flex;align-items:center;gap:6px;font-weight:normal">
              <input type="checkbox" v-model="newTask.user_ids" :value="c.id" style="width:auto" />
              {{ c.full_name }}
            </label>
          </div>
        </div>
        <button class="btn" type="submit" :disabled="taskSubmitting">
          {{ taskSubmitting ? 'Přidávám…' : 'Přidat úkol' }}
        </button>
      </form>
      <p v-if="taskError" class="error">{{ taskError }}</p>

      <table v-if="upcomingTasks.length" style="margin-top:14px">
        <thead>
          <tr><th>Den</th><th>Kurýr</th><th>Text</th><th>Stav</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="t in upcomingTasks" :key="t.id">
            <td>{{ t.date }}</td>
            <td>{{ courierName(t.user_id) }}</td>
            <td>{{ t.text }}</td>
            <td>
              <span class="badge" :class="t.done ? 'paid' : 'unpaid'">{{ t.done ? 'hotovo' : 'čeká' }}</span>
            </td>
            <td>
              <button
                class="btn secondary"
                style="color:var(--red)"
                :disabled="deletingTaskId === t.id"
                @click="deleteTask(t)"
              >
                {{ deletingTaskId === t.id ? 'Mažu…' : 'Smazat' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
