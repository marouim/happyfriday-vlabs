<script setup>
import { mdiDelete, mdiMapMarker, mdiPlay, mdiPlus, mdiServer, mdiStop } from '@mdi/js'
import { computed, onMounted, onUnmounted, ref } from 'vue'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''
const activePage = ref('virtual')

const laboratories = ref([])
const laboratoryTypes = ref([])
const physicalLocations = ref([])
const physicalRequests = ref([])

const virtualHeaders = [
  { title: 'Laboratoire', key: 'name' },
  { title: 'Type', key: 'type' },
  { title: 'Statut', key: 'status', align: 'end' },
  { title: 'URL', key: 'url', align: 'end', sortable: false },
  { title: 'Actions', key: 'actions', align: 'end', sortable: false },
]

const requestHeaders = [
  { title: 'Demandeur', key: 'requesterName' },
  { title: 'Location', key: 'location' },
  { title: 'Serveurs', key: 'serverCount', align: 'end' },
  { title: 'Statut', key: 'status', align: 'end' },
]

const labDialogOpen = ref(false)
const requestDialogOpen = ref(false)
const deletionDialogOpen = ref(false)
const laboratoryToDelete = ref(null)

const labForm = ref(null)
const requestForm = ref(null)
const name = ref('')
const type = ref(null)
const requesterName = ref('')
const locationId = ref(null)
const serverCount = ref(1)
const requestPurpose = ref('')

const pendingStatuses = ref({})
const pendingDeletions = ref({})
const labsLoading = ref(false)
const typesLoading = ref(false)
const physicalLoading = ref(false)
const labSaving = ref(false)
const requestSaving = ref(false)
const alertMessage = ref('')
let progressPollInterval = null

const activeLabs = computed(() =>
  laboratories.value.filter((laboratory) => laboratory.status === 'running').length,
)

const totalPhysicalServers = computed(() =>
  physicalLocations.value.reduce((total, location) => total + location.serverCapacity, 0),
)

const availablePhysicalServers = computed(() =>
  physicalLocations.value.reduce((total, location) => total + location.availableServers, 0),
)

const selectedLocation = computed(() =>
  physicalLocations.value.find((location) => location.id === locationId.value),
)

const statusColors = {
  approved: 'success',
  deleting: 'info',
  failed: 'error',
  fulfilled: 'success',
  rejected: 'error',
  requested: 'info',
  running: 'success',
  starting: 'info',
  stopped: 'warning',
  stopping: 'info',
  terminated: 'error',
}

const statusLabels = {
  approved: 'Approved',
  deleting: 'Deleting',
  failed: 'Failed',
  fulfilled: 'Fulfilled',
  rejected: 'Rejected',
  requested: 'Requested',
  running: 'Running',
  starting: 'Starting',
  stopped: 'Stopped',
  stopping: 'Stopping',
  terminated: 'Terminated',
}

const required = (value) => Boolean(value?.trim?.() || value) || 'Ce champ est requis.'
const positiveServerCount = (value) => Number(value) > 0 || 'Demandez au moins un serveur.'
const availableServerCount = (value) =>
  !selectedLocation.value ||
  Number(value) <= selectedLocation.value.availableServers ||
  'Pas assez de serveurs disponibles.'

function resetLabForm() {
  name.value = ''
  type.value = null
  labForm.value?.resetValidation()
}

function resetRequestForm() {
  requesterName.value = ''
  locationId.value = physicalLocations.value[0]?.id ?? null
  serverCount.value = 1
  requestPurpose.value = ''
  requestForm.value?.resetValidation()
}

function openCreateDialog() {
  if (activePage.value === 'physical') {
    resetRequestForm()
    requestDialogOpen.value = true
    return
  }

  labDialogOpen.value = true
}

function closeLabDialog() {
  labDialogOpen.value = false
  resetLabForm()
}

function closeRequestDialog() {
  requestDialogOpen.value = false
  resetRequestForm()
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
  return isProgressStatus(laboratory.status) || isStatusPending(laboratory) || isDeletionPending(laboratory)
}

function isProgressStatus(status) {
  return status === 'deleting' || status === 'starting' || status === 'stopping'
}

function formatDate(value) {
  if (!value) {
    return ''
  }

  return new Intl.DateTimeFormat('en-CA', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function stopProgressPolling() {
  if (progressPollInterval) {
    window.clearInterval(progressPollInterval)
    progressPollInterval = null
  }
}

function syncProgressPolling() {
  const hasInProgressLaboratory = laboratories.value.some(
    (laboratory) => isProgressStatus(laboratory.status),
  )

  if (!hasInProgressLaboratory) {
    stopProgressPolling()
    return
  }

  if (!progressPollInterval) {
    progressPollInterval = window.setInterval(() => {
      loadLaboratories(false)
    }, 3000)
  }
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

async function loadLaboratories(showLoading = true) {
  if (showLoading) {
    labsLoading.value = true
  }
  alertMessage.value = ''

  try {
    laboratories.value = await requestApi('/api/vlabs')
    syncProgressPolling()
  } catch (error) {
    alertMessage.value = `Impossible de charger les laboratoires : ${error.message}`
  } finally {
    if (showLoading) {
      labsLoading.value = false
    }
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

async function loadPhysicalLabs() {
  physicalLoading.value = true
  alertMessage.value = ''

  try {
    const [locations, requests] = await Promise.all([
      requestApi('/api/physical-lab-locations'),
      requestApi('/api/physical-lab-requests'),
    ])
    physicalLocations.value = locations
    physicalRequests.value = requests
    if (!locationId.value) {
      locationId.value = locations[0]?.id ?? null
    }
  } catch (error) {
    alertMessage.value = `Impossible de charger les labs physiques : ${error.message}`
  } finally {
    physicalLoading.value = false
  }
}

async function updateStatus(laboratory, status) {
  if (isStatusPending(laboratory)) {
    return
  }

  alertMessage.value = ''
  pendingStatuses.value[laboratory.id] = status

  try {
    const updatedLaboratory = await requestApi(`/api/vlabs/${laboratory.id}`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    })
    Object.assign(laboratory, updatedLaboratory)
    syncProgressPolling()
  } catch (error) {
    alertMessage.value = `Impossible de changer le statut : ${error.message}`
  } finally {
    delete pendingStatuses.value[laboratory.id]
  }
}

async function addLaboratory() {
  const { valid } = await labForm.value.validate()

  if (!valid) {
    return
  }

  alertMessage.value = ''
  labSaving.value = true

  try {
    const createdLaboratory = await requestApi('/api/vlabs', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value.trim(),
        type: type.value,
      }),
    })
    laboratories.value.unshift(createdLaboratory)
    closeLabDialog()
  } catch (error) {
    alertMessage.value = `Impossible d'ajouter le laboratoire : ${error.message}`
  } finally {
    labSaving.value = false
  }
}

async function requestPhysicalServers() {
  const { valid } = await requestForm.value.validate()

  if (!valid) {
    return
  }

  alertMessage.value = ''
  requestSaving.value = true

  try {
    const createdRequest = await requestApi('/api/physical-lab-requests', {
      method: 'POST',
      body: JSON.stringify({
        requesterName: requesterName.value.trim(),
        locationId: locationId.value,
        serverCount: Number(serverCount.value),
        purpose: requestPurpose.value.trim(),
      }),
    })
    physicalRequests.value.unshift(createdRequest)
    const location = physicalLocations.value.find((item) => item.id === locationId.value)
    if (location) {
      location.availableServers -= Number(serverCount.value)
    }
    closeRequestDialog()
  } catch (error) {
    alertMessage.value = `Impossible de creer la demande : ${error.message}`
  } finally {
    requestSaving.value = false
  }
}

async function deleteLaboratory() {
  const laboratory = laboratoryToDelete.value

  if (!laboratory || isActionPending(laboratory)) {
    return
  }

  alertMessage.value = ''
  pendingDeletions.value[laboratory.id] = true

  try {
    const updatedLaboratory = await requestApi(`/api/vlabs/${laboratory.id}`, { method: 'DELETE' })
    Object.assign(laboratory, updatedLaboratory)
    syncProgressPolling()
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
  loadPhysicalLabs()
})

onUnmounted(() => {
  stopProgressPolling()
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
        <v-tabs v-model="activePage" class="desktop-tabs" color="primary" density="comfortable">
          <v-tab value="virtual">Virtual labs</v-tab>
          <v-tab value="physical">Physical labs</v-tab>
        </v-tabs>
        <v-btn
          color="primary"
          variant="flat"
          size="large"
          rounded="lg"
          :prepend-icon="mdiPlus"
          @click="openCreateDialog"
        >
          {{ activePage === 'physical' ? 'Request' : 'Add' }}
        </v-btn>
      </v-container>
    </v-app-bar>

    <v-main>
      <v-container class="page-container">
        <v-tabs v-model="activePage" class="mobile-tabs" color="primary" grow>
          <v-tab value="virtual">Virtual</v-tab>
          <v-tab value="physical">Physical</v-tab>
        </v-tabs>

        <v-alert
          v-if="alertMessage"
          type="error"
          variant="tonal"
          closable
          class="mb-5"
          @click:close="alertMessage = ''"
        >
          {{ alertMessage }}
        </v-alert>

        <v-window v-model="activePage">
          <v-window-item value="virtual">
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
                  :prepend-icon="mdiPlus"
                  @click="labDialogOpen = true"
                >
                  Add
                </v-btn>
              </div>

              <v-data-table
                :headers="virtualHeaders"
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
                    :text="statusLabels[item.status] || item.status"
                    size="small"
                    variant="tonal"
                    class="status-chip"
                  >
                    <template v-if="isProgressStatus(item.status)" #prepend>
                      <v-progress-circular indeterminate size="14" width="2" class="mr-2" />
                    </template>
                  </v-chip>
                </template>

                <template #item.actions="{ item }">
                  <div class="laboratory-actions">
                    <v-progress-circular
                      v-if="isProgressStatus(item.status)"
                      color="info"
                      indeterminate
                      size="28"
                      width="3"
                    />
                    <v-btn
                      v-else-if="item.status === 'running'"
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
                      v-else-if="item.status === 'stopped' || item.status === 'failed'"
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
                      :disabled="item.status !== 'stopped' || isActionPending(item)"
                      :aria-label="`Delete ${item.name}`"
                      @click="openDeletionDialog(item)"
                    />
                  </div>
                </template>
              </v-data-table>
            </v-card>
          </v-window-item>

          <v-window-item value="physical">
            <section class="hero">
              <div>
                <p class="eyebrow">Physical infrastructure</p>
                <h1>Physical labs</h1>
                <p class="intro">
                  Request bare-metal servers from a location and track demand by site.
                </p>
              </div>

              <v-card class="summary-card" elevation="0">
                <p class="summary-label">Available servers</p>
                <p class="summary-value">{{ availablePhysicalServers }}</p>
                <p class="summary-detail">of {{ totalPhysicalServers }} physical servers</p>
              </v-card>
            </section>

            <div class="location-grid">
              <v-card
                v-for="location in physicalLocations"
                :key="location.id"
                class="location-card"
                elevation="0"
              >
                <div class="location-card-heading">
                  <v-icon :icon="mdiMapMarker" color="primary" />
                  <div>
                    <h2>{{ location.name }}</h2>
                    <p>{{ location.description }}</p>
                  </div>
                </div>
                <div class="capacity-row">
                  <span>{{ location.availableServers }} available</span>
                  <span>{{ location.serverCapacity }} total</span>
                </div>
                <v-progress-linear
                  :model-value="(location.availableServers / location.serverCapacity) * 100"
                  color="primary"
                  height="8"
                  rounded
                />
              </v-card>
            </div>

            <v-card class="table-card physical-table-card" elevation="0">
              <div class="table-heading">
                <div>
                  <h2>Server requests</h2>
                  <p>{{ physicalRequests.length }} physical lab requests</p>
                </div>
                <v-btn
                  class="mobile-add"
                  color="primary"
                  variant="flat"
                  rounded="lg"
                  :prepend-icon="mdiPlus"
                  @click="requestDialogOpen = true"
                >
                  Request
                </v-btn>
              </div>

              <v-data-table
                :headers="requestHeaders"
                :items="physicalRequests"
                item-value="id"
                hide-default-footer
                :loading="physicalLoading"
                loading-text="Chargement des demandes..."
                class="laboratory-table"
              >
                <template #item.requesterName="{ item }">
                  <div class="lab-name-cell">
                    <span class="lab-avatar physical-avatar">
                      <v-icon :icon="mdiServer" size="18" />
                    </span>
                    <span>
                      <strong>{{ item.requesterName }}</strong>
                      <small>{{ item.purpose || formatDate(item.createdAt) }}</small>
                    </span>
                  </div>
                </template>

                <template #item.serverCount="{ item }">
                  {{ item.serverCount }}
                </template>

                <template #item.status="{ item }">
                  <v-chip
                    :color="statusColors[item.status]"
                    :text="statusLabels[item.status] || item.status"
                    size="small"
                    variant="tonal"
                    class="status-chip"
                  />
                </template>
              </v-data-table>
            </v-card>
          </v-window-item>
        </v-window>
      </v-container>
    </v-main>

    <v-dialog v-model="labDialogOpen" max-width="500" @after-leave="resetLabForm">
      <v-card class="dialog-card" rounded="xl">
        <v-card-title>Add a laboratory</v-card-title>
        <v-card-subtitle>Create a new self-serve virtual environment.</v-card-subtitle>

        <v-card-text>
          <v-form ref="labForm" @submit.prevent="addLaboratory">
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
          <v-btn variant="text" rounded="lg" @click="closeLabDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            rounded="lg"
            :prepend-icon="mdiPlus"
            :loading="labSaving"
            @click="addLaboratory"
          >
            Add
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="requestDialogOpen" max-width="560" @after-leave="resetRequestForm">
      <v-card class="dialog-card" rounded="xl">
        <v-card-title>Request physical servers</v-card-title>
        <v-card-subtitle>Reserve physical capacity from a lab location.</v-card-subtitle>

        <v-card-text>
          <v-form ref="requestForm" @submit.prevent="requestPhysicalServers">
            <v-text-field
              v-model="requesterName"
              label="Requester"
              placeholder="Example: Martin"
              variant="outlined"
              color="primary"
              :rules="[required]"
              class="mb-3"
            />
            <v-select
              v-model="locationId"
              label="Location"
              :items="physicalLocations"
              item-title="name"
              item-value="id"
              :loading="physicalLoading"
              :disabled="physicalLoading || physicalLocations.length === 0"
              variant="outlined"
              color="primary"
              :rules="[required]"
              class="mb-3"
            />
            <v-text-field
              v-model="serverCount"
              label="Servers"
              type="number"
              :min="1"
              :max="selectedLocation?.availableServers || 1"
              variant="outlined"
              color="primary"
              :rules="[positiveServerCount, availableServerCount]"
              class="mb-3"
            />
            <v-textarea
              v-model="requestPurpose"
              label="Purpose"
              placeholder="Example: Firmware validation on physical hardware"
              variant="outlined"
              color="primary"
              rows="3"
            />
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" rounded="lg" @click="closeRequestDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            rounded="lg"
            :prepend-icon="mdiServer"
            :loading="requestSaving"
            @click="requestPhysicalServers"
          >
            Request
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
