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
  series_id: number
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

interface MyFieldSummary { key: string; label: string; total: number; avg: number }
interface MySummary { year: number; month: number; entries_count: number; fields: MyFieldSummary[] }

interface TaskGroup {
  series_id: number
  text: string
  userIds: number[]
  dates: string[]
  doneCount: number
  tasks: HomeTask[]
}

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
  if (isAdmin.value) return
  checklist.value = await api.get<Checklist>('/checklist/today')
}

const summary = ref<MySummary | null>(null)
const summaryMonthLabel = computed(() => {
  if (!summary.value) return ''
  return new Date(summary.value.year, summary.value.month - 1, 1).toLocaleDateString('cs-CZ', {
    month: 'long',
    year: 'numeric',
  })
})

function roundStat(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

async function loadSummary() {
  if (isAdmin.value) return
  summary.value = await api.get<MySummary>('/performance/my-summary')
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

const taskGroups = computed<TaskGroup[]>(() => {
  const map = new Map<number, TaskGroup>()
  for (const t of upcomingTasks.value) {
    let g = map.get(t.series_id)
    if (!g) {
      g = { series_id: t.series_id, text: t.text, userIds: [], dates: [], doneCount: 0, tasks: [] }
      map.set(t.series_id, g)
    }
    if (!g.userIds.includes(t.user_id)) g.userIds.push(t.user_id)
    if (!g.dates.includes(t.date)) g.dates.push(t.date)
    if (t.done) g.doneCount++
    g.tasks.push(t)
  }
  return [...map.values()].sort((a, b) => (a.dates[0] ?? '').localeCompare(b.dates[0] ?? ''))
})

function groupDateLabel(g: TaskGroup): string {
  if (g.dates.length === 1) return g.dates[0] ?? ''
  return `${g.dates[0]} → ${g.dates[g.dates.length - 1]} (${g.dates.length}×)`
}

function groupCourierLabel(g: TaskGroup): string {
  return g.userIds.map(courierName).join(', ')
}

const newTask = ref({ text: '', date: new Date().toISOString().slice(0, 10), user_ids: [] as number[] })
const allSelected = computed({
  get: () => couriers.value.length > 0 && newTask.value.user_ids.length === couriers.value.length,
  set: (val: boolean) => {
    newTask.value.user_ids = val ? couriers.value.map((c) => c.id) : []
  },
})

type RepeatMode = 'once' | 'week1' | 'week2' | 'month'
const repeatMode = ref<RepeatMode>('once')
const repeatUntil = ref('')
const weekdayOptions = [
  { value: 0, label: 'Po' },
  { value: 1, label: 'Út' },
  { value: 2, label: 'St' },
  { value: 3, label: 'Čt' },
  { value: 4, label: 'Pá' },
]
const selectedWeekdays = ref<number[]>([])
const showWeekdays = computed(() => repeatMode.value === 'week1' || repeatMode.value === 'week2')

// Datum -> den v týdnu podle Python konvence (0 = pondělí .. 4 = pátek), aby se
// shodovala s tím, co čeká backend (date.weekday()).
function weekdayOfDate(iso: string): number {
  const jsDay = new Date(`${iso}T00:00:00`).getDay() // 0 = neděle .. 6 = sobota
  return (jsDay + 6) % 7
}

// Když admin přepne na opakování po týdnech, rovnou předvyplní den v týdnu podle
// zvoleného data - ať nemusí zaškrtávat to samé znovu ručně.
function onRepeatModeChange() {
  if (showWeekdays.value && !selectedWeekdays.value.length) {
    const wd = weekdayOfDate(newTask.value.date)
    if (wd <= 4) selectedWeekdays.value = [wd]
  }
}

const taskSubmitting = ref(false)
const taskError = ref('')
const deletingTaskId = ref<number | null>(null)
const deletingSeriesId = ref<number | null>(null)
const expandedSeriesId = ref<number | null>(null)

function courierName(userId: number) {
  return allUsers.value.find((u) => u.id === userId)?.full_name || `#${userId}`
}

function toggleExpanded(seriesId: number) {
  expandedSeriesId.value = expandedSeriesId.value === seriesId ? null : seriesId
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
  if (repeatMode.value !== 'once' && !repeatUntil.value) {
    taskError.value = 'Vyber datum, do kdy se má úkol opakovat'
    return
  }
  if (showWeekdays.value && !selectedWeekdays.value.length) {
    taskError.value = 'Vyber aspoň jeden pracovní den, ve kterém se má úkol opakovat'
    return
  }
  taskSubmitting.value = true
  try {
    await api.post('/checklist/tasks', {
      ...newTask.value,
      repeat_unit: repeatMode.value === 'once' ? null : repeatMode.value === 'month' ? 'month' : 'week',
      repeat_interval: repeatMode.value === 'week2' ? 2 : 1,
      weekdays: showWeekdays.value ? selectedWeekdays.value : null,
      repeat_until: repeatMode.value === 'once' ? null : repeatUntil.value,
    })
    newTask.value = { text: '', date: new Date().toISOString().slice(0, 10), user_ids: [] }
    repeatMode.value = 'once'
    repeatUntil.value = ''
    selectedWeekdays.value = []
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

async function deleteSeries(g: TaskGroup) {
  if (!window.confirm(`Smazat celou sérii "${g.text}" (${g.tasks.length} položek)?`)) return
  deletingSeriesId.value = g.series_id
  try {
    await api.delete(`/checklist/tasks/series/${g.series_id}`)
    upcomingTasks.value = upcomingTasks.value.filter((t) => t.series_id !== g.series_id)
    await load()
  } finally {
    deletingSeriesId.value = null
  }
}

onMounted(async () => {
  await Promise.all([load(), loadAdminData(), loadSummary()])
})
</script>

<template>
  <div>
    <h1><span class="eyebrow">Dnešní směna</span>Ahoj, {{ user?.full_name }}</h1>
    <p class="today-date">{{ todayLabel }}</p>

    <template v-if="!isAdmin">
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
    </template>

    <div class="card checklist-card" v-else>
      <div class="checklist-header">
        <h3>Úkoly kurýra <span class="badge unpaid" style="margin-left:8px;font-weight:500">jen náhled</span></h3>
      </div>
      <p style="font-size:12px;color:var(--muted);margin:-4px 20px 8px">
        Takto vidí každý kurýr svoje úkoly na hlavní stránce. Tady si to jen prohlédneš - kliknutí nic
        neukládá. Jednorázové nebo opakující se úkoly navíc kurýrům přidáš níže.
      </p>
      <ul class="checklist">
        <li class="checklist-item done">
          <button type="button" class="check-toggle" disabled>
            <span class="check-box checked"></span>
            <span class="check-label">Zkontrolovat auto</span>
          </button>
        </li>
        <li class="checklist-item">
          <button type="button" class="check-toggle" disabled>
            <span class="check-box"></span>
            <span class="check-label">Natankovat</span>
          </button>
        </li>
        <li class="checklist-item">
          <button type="button" class="check-toggle" disabled>
            <span class="check-box"></span>
            <span class="check-label">
              Vyplnit formulář trasy
              <span class="check-hint">Odškrtne se, až kurýr formulář výkonu vyplní celý bez přeskočení</span>
            </span>
          </button>
        </li>
      </ul>
    </div>

    <div class="card" v-if="!isAdmin && summary">
      <h3 style="margin-top:0">Tvůj měsíc <span style="color:var(--muted);font-weight:400">· {{ summaryMonthLabel }}</span></h3>
      <p v-if="!summary.entries_count" style="color:var(--muted);margin:0">
        Tento měsíc zatím nemáš vyplněný žádný formulář výkonu.
      </p>
      <template v-else>
        <p style="font-size:13px;color:var(--muted);margin-top:-6px">
          Vyplněných dní: {{ summary.entries_count }}
        </p>
        <div class="stat-grid">
          <div class="stat-item" v-for="f in summary.fields" :key="f.key">
            <div class="stat-label">{{ f.label }}</div>
            <div class="stat-total">{{ roundStat(f.total) }}</div>
            <div class="stat-avg">Ø {{ roundStat(f.avg) }} / den</div>
          </div>
        </div>
      </template>
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

        <div class="form-row">
          <div class="field">
            <label>Opakování</label>
            <select v-model="repeatMode" @change="onRepeatModeChange">
              <option value="once">Jednorázově - jen zvolený den</option>
              <option value="week1">Každý týden</option>
              <option value="week2">Každé 2 týdny</option>
              <option value="month">Každý měsíc</option>
            </select>
          </div>
          <div class="field" v-if="repeatMode !== 'once'">
            <label>Opakovat do</label>
            <input v-model="repeatUntil" type="date" :min="newTask.date" />
          </div>
        </div>

        <div class="field" v-if="showWeekdays">
          <label>V kterých dnech</label>
          <div style="display:flex;gap:12px">
            <label v-for="w in weekdayOptions" :key="w.value" style="display:flex;align-items:center;gap:6px;font-weight:normal">
              <input type="checkbox" v-model="selectedWeekdays" :value="w.value" style="width:auto" />
              {{ w.label }}
            </label>
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

      <table v-if="taskGroups.length" style="margin-top:14px">
        <thead>
          <tr><th>Den</th><th>Kurýr</th><th>Text</th><th>Stav</th><th></th></tr>
        </thead>
        <tbody>
          <template v-for="g in taskGroups" :key="g.series_id">
            <tr>
              <td>{{ groupDateLabel(g) }}</td>
              <td>{{ groupCourierLabel(g) }}</td>
              <td>{{ g.text }}</td>
              <td>{{ g.doneCount }}/{{ g.tasks.length }} hotovo</td>
              <td style="white-space:nowrap">
                <button v-if="g.tasks.length > 1" class="btn secondary" @click="toggleExpanded(g.series_id)">
                  {{ expandedSeriesId === g.series_id ? 'Skrýt' : 'Zobrazit' }}
                </button>
                <button
                  class="btn secondary"
                  style="margin-left:6px;color:var(--red)"
                  :disabled="deletingSeriesId === g.series_id"
                  @click="deleteSeries(g)"
                >
                  {{ deletingSeriesId === g.series_id ? 'Mažu…' : (g.tasks.length > 1 ? 'Smazat vše' : 'Smazat') }}
                </button>
              </td>
            </tr>
            <tr v-if="expandedSeriesId === g.series_id">
              <td colspan="5" style="background:var(--paper)">
                <table style="margin:0">
                  <tbody>
                    <tr v-for="t in g.tasks" :key="t.id">
                      <td style="width:110px">{{ t.date }}</td>
                      <td>{{ courierName(t.user_id) }}</td>
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
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
