<script setup>
import { mdiDelete, mdiPlay, mdiStop } from '@mdi/js'
import { computed, onMounted, ref } from 'vue'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''
const laboratories = ref([])
const laboratoryTypes = ref([])

const headers = [
  { title: 'Laboratoire', key: 'name' },
  { title: 'Type', key: 'type' },
  { title: 'Statut', key: 'status', align: 'end' },
  { title: 'Actions', key: 'actions', align: 'end', sortable: false },
]

const dialogOpen = ref(false)
const deletionDialogOpen = ref(false)
const laboratoryToDelete = ref(null)
const form = ref(null)
const name = ref('')
const type = ref(null)
const pendingStatuses = ref({})
const pendingDeletions = ref({})
const labsLoading = ref(false)
const typesLoading = ref(false)
const formSaving = ref(false)
const alertMessage = ref('')

const activeLabs = computed(() =>
  laboratories.value.filter((laboratory) => laboratory.status === 'running').length,
)

const statusColors = {
  running: 'success',
  stopped: 'warning',
  terminated: 'error',
}

const required = (value) => Boolean(value?.trim?.() || value) || 'Ce champ est requis.'

function resetForm() {
  name.value = ''
  type.value = null
  form.value?.resetValidation()
}

function closeDialog() {
  dialogOpen.value = false
  resetForm()
}

function openDeletionDialog(laboratory) {
  if (isActionPending(laboratory)) {
    return
  }

  laboratoryToDelete.value = laboratory
  deletionDialogOpen.value = true
}

function closeDeletionDialog() {
  if (laboratoryToDelete.value && isDeletionPending(laboratoryToDelete.value)) {
    return
  }

  deletionDialogOpen.value = false
  laboratoryToDelete.value = null
}

function isStatusPending(laboratory) {
  return Boolean(pendingStatuses.value[laboratory.id])
}

function isDeletionPending(laboratory) {
  return Boolean(pendingDeletions.value[laboratory.id])
}

function isActionPending(laboratory) {
  return isStatusPending(laboratory) || isDeletionPending(laboratory)
}

function wait(duration) {
  return new Promise((resolve) => window.setTimeout(resolve, duration))
}

async function requestApi(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  const body = await response.json()

  if (!response.ok) {
    throw new Error(body.error || 'La requete API a echoue.')
  }

  return body
}

async function loadLaboratories() {
  labsLoading.value = true
  alertMessage.value = ''

  try {
    laboratories.value = await requestApi('/api/vlabs')
  } catch (error) {
    alertMessage.value = `Impossible de charger les laboratoires : ${error.message}`
  } finally {
    labsLoading.value = false
  }
}

async function loadLaboratoryTypes() {
  typesLoading.value = true

  try {
    laboratoryTypes.value = await requestApi('/api/vlabtype')
  } catch (error) {
    alertMessage.value = `Impossible de charger les types de laboratoire : ${error.message}`
  } finally {
    typesLoading.value = false
  }
}

async function updateStatus(laboratory, status) {
  if (isStatusPending(laboratory)) {
    return
  }

  alertMessage.value = ''
  pendingStatuses.value[laboratory.id] = status

  try {
    const [updatedLaboratory] = await Promise.all([
      requestApi(`/api/vlabs/${laboratory.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
      }),
      wait(3000),
    ])
    Object.assign(laboratory, updatedLaboratory)
  } catch (error) {
    alertMessage.value = `Impossible de changer le statut : ${error.message}`
  } finally {
    delete pendingStatuses.value[laboratory.id]
  }
}

async function addLaboratory() {
  const { valid } = await form.value.validate()

  if (!valid) {
    return
  }

  alertMessage.value = ''
  formSaving.value = true

  try {
    const createdLaboratory = await requestApi('/api/vlabs', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value.trim(),
        type: type.value,
      }),
    })
    laboratories.value.unshift(createdLaboratory)
    closeDialog()
  } catch (error) {
    alertMessage.value = `Impossible d'ajouter le laboratoire : ${error.message}`
  } finally {
    formSaving.value = false
  }
}

async function deleteLaboratory() {
  const laboratory = laboratoryToDelete.value

  if (!laboratory) {
    return
  }

  if (isActionPending(laboratory)) {
    return
  }

  alertMessage.value = ''
  pendingDeletions.value[laboratory.id] = true

  try {
    await requestApi(`/api/vlabs/${laboratory.id}`, { method: 'DELETE' })
    laboratories.value = laboratories.value.filter((entry) => entry.id !== laboratory.id)
    deletionDialogOpen.value = false
    laboratoryToDelete.value = null
  } catch (error) {
    alertMessage.value = `Impossible de supprimer le laboratoire : ${error.message}`
  } finally {
    delete pendingDeletions.value[laboratory.id]
  }
}

onMounted(() => {
  loadLaboratories()
  loadLaboratoryTypes()
})
</script>

<template>
  <v-app>
    <v-app-bar flat class="header-bar">
      <v-container class="d-flex align-center">
        <div class="brand-mark">VL</div>
        <div>
          <p class="brand-name">Virtual Labs</p>
          <p class="brand-subtitle">Self-serve management</p>
        </div>
        <v-spacer />
        <v-btn color="primary" variant="flat" size="large" rounded="lg" @click="dialogOpen = true">
          Add
        </v-btn>
      </v-container>
    </v-app-bar>

    <v-main>
      <v-container class="page-container">
        <section class="hero">
          <div>
            <p class="eyebrow">Laboratory operations</p>
            <h1>Virtual laboratories</h1>
            <p class="intro">
              Provision and monitor self-serve simulation environments from one workspace.
            </p>
          </div>

          <v-card class="summary-card" elevation="0">
            <p class="summary-label">Running now</p>
            <p class="summary-value">{{ activeLabs }}</p>
            <p class="summary-detail">of {{ laboratories.length }} laboratories active</p>
          </v-card>
        </section>

        <v-card class="table-card" elevation="0">
          <div class="table-heading">
            <div>
              <h2>Laboratories</h2>
              <p>{{ laboratories.length }} available environments</p>
            </div>
            <v-btn
              class="mobile-add"
              color="primary"
              variant="flat"
              rounded="lg"
              @click="dialogOpen = true"
            >
              Add
            </v-btn>
          </div>

          <v-alert
            v-if="alertMessage"
            type="error"
            variant="tonal"
            closable
            class="mx-6 mb-4"
            @click:close="alertMessage = ''"
          >
            {{ alertMessage }}
          </v-alert>

          <v-data-table
            :headers="headers"
            :items="laboratories"
            item-value="id"
            hide-default-footer
            :loading="labsLoading"
            loading-text="Chargement des laboratoires..."
            class="laboratory-table"
          >
            <template #item.name="{ item }">
              <div class="lab-name-cell">
                <span class="lab-avatar">{{ item.name.charAt(0) }}</span>
                <span>{{ item.name }}</span>
              </div>
            </template>

            <template #item.status="{ item }">
              <v-chip
                :color="statusColors[item.status]"
                :text="item.status"
                size="small"
                variant="tonal"
                class="status-chip"
              />
            </template>

            <template #item.actions="{ item }">
              <div class="laboratory-actions">
                <v-btn
                  v-if="item.status === 'running'"
                  :icon="mdiStop"
                  color="error"
                  variant="tonal"
                  size="small"
                  :loading="isStatusPending(item)"
                  :disabled="isDeletionPending(item)"
                  :aria-label="`Stop ${item.name}`"
                  @click="updateStatus(item, 'stopped')"
                />
                <v-btn
                  v-else-if="item.status === 'stopped'"
                  :icon="mdiPlay"
                  color="success"
                  variant="tonal"
                  size="small"
                  :loading="isStatusPending(item)"
                  :disabled="isDeletionPending(item)"
                  :aria-label="`Start ${item.name}`"
                  @click="updateStatus(item, 'running')"
                />
                <v-btn
                  :icon="mdiDelete"
                  color="error"
                  variant="text"
                  size="small"
                  :loading="isDeletionPending(item)"
                  :disabled="item.status !== 'stopped' || isStatusPending(item)"
                  :aria-label="`Delete ${item.name}`"
                  @click="openDeletionDialog(item)"
                />
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-container>
    </v-main>

    <v-dialog v-model="dialogOpen" max-width="500" @after-leave="resetForm">
      <v-card class="dialog-card" rounded="xl">
        <v-card-title>Add a laboratory</v-card-title>
        <v-card-subtitle>Create a new self-serve virtual environment.</v-card-subtitle>

        <v-card-text>
          <v-form ref="form" @submit.prevent="addLaboratory">
            <v-text-field
              v-model="name"
              label="Laboratory name"
              placeholder="Example: Pilot training session"
              variant="outlined"
              color="primary"
              :rules="[required]"
              class="mb-3"
            />
            <v-select
              v-model="type"
              label="Type"
              placeholder="Select a laboratory type"
              :items="laboratoryTypes"
              :loading="typesLoading"
              :disabled="typesLoading || laboratoryTypes.length === 0"
              variant="outlined"
              color="primary"
              :rules="[required]"
            />
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" rounded="lg" @click="closeDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            rounded="lg"
            :loading="formSaving"
            @click="addLaboratory"
          >
            Add
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deletionDialogOpen" max-width="460" persistent>
      <v-card class="dialog-card" rounded="xl">
        <v-card-title>Delete laboratory?</v-card-title>
        <v-card-text class="deletion-message">
          Are you sure you want to delete
          <strong>{{ laboratoryToDelete?.name }}</strong>?
          This action cannot be undone.
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            variant="text"
            rounded="lg"
            :disabled="laboratoryToDelete && isDeletionPending(laboratoryToDelete)"
            @click="closeDeletionDialog"
          >
            Cancel
          </v-btn>
          <v-btn
            color="error"
            variant="flat"
            rounded="lg"
            :loading="laboratoryToDelete && isDeletionPending(laboratoryToDelete)"
            @click="deleteLaboratory"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>
