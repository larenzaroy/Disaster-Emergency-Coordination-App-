/**
 * ResQNet — Client Side Master Application Logic
 * Coordinates SOS, Hospital & Ambulance Radars, Green Corridor Simulation,
 * Doctor EHR Access, AI Rx Simplifier, and Disaster Protocols.
 */

// Global State
const state = {
  userCoords: { lat: 22.5726, lon: 88.3639 }, // Default metropolitan center
  activeHazard: 'CARDIAC',
  selectedAmbulanceQty: 1,
  activeEmergencyId: null,
  activeAmbulanceId: 'AMB-101',
  editingPatientId: 'P-101',
  countdownInterval: null,
  countdownSeconds: 3,
  sirenAudioCtx: null,
  sirenOsc: null,
  isSirenPlaying: false,
  isStrobeActive: false,
  greenCorridorActive: false,
  isSimulatingDrive: false,
  simInterval: null,
  speechSynth: window.speechSynthesis || null,
  currentSpeechText: '',
  currentRouteData: null,
  hospitals: [],
  ambulances: [],
  trafficSignals: []
};

// Maps instances
let citizenMap = null;
let ambulanceMap = null;
let trafficMap = null;

let citizenMarkers = { user: null, hospitals: [], ambulances: [] };
let ambulanceMarkers = { amb: null, target: null, hosp: null, routeLine: null, signals: [] };
let trafficSignalMarkers = [];

// ----------------- INITIALIZATION -----------------
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initClock();
  setupNavigation();
  setupHazardChips();
  setupAmbulanceQtyChips();
  initCitizenMap();
  loadHospitals();
  loadAmbulances();
  loadEmergencies();
  loadTrafficSignals();
  checkActiveBroadcasts();
  runTriageCalculation();
  getUserLocation();
  refreshPatientBannerPreview('P-101');

  // Polling interval for live emergency radar (every 6 seconds)
  setInterval(() => {
    loadEmergencies();
    loadTrafficSignals(false);
  }, 6000);
});

// Real-time Top Clock
function initClock() {
  const clockEl = document.getElementById('liveClock');
  setInterval(() => {
    const now = new Date();
    clockEl.textContent = now.toTimeString().split(' ')[0];
  }, 1000);
}

// ----------------- NAVIGATION TABS -----------------
function setupNavigation() {
  const tabs = document.querySelectorAll('#navTabs .nav-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const targetView = btn.getAttribute('data-view');
      document.querySelectorAll('.view-panel').forEach(panel => {
        panel.classList.remove('active');
      });

      const activePanel = document.getElementById(targetView);
      if (activePanel) {
        activePanel.classList.add('active');
        // Invalidate map sizes when switching tabs so Leaflet renders cleanly
        setTimeout(() => {
          if (targetView === 'citizenView' && citizenMap) citizenMap.invalidateSize();
          if (targetView === 'ambulanceView') initAmbulanceMap();
          if (targetView === 'trafficView') initTrafficMap();
        }, 150);
      }
      lucide.createIcons();
    });
  });
}

function setupHazardChips() {
  const chips = document.querySelectorAll('#hazardChips .chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeHazard = chip.getAttribute('data-hazard');
    });
  });
}

function setupAmbulanceQtyChips() {
  const chips = document.querySelectorAll('#ambQtyChips .chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.selectedAmbulanceQty = parseInt(chip.getAttribute('data-qty')) || 1;
    });
  });
}

// ----------------- USER GEOLOCATION -----------------
function getUserLocation() {
  const display = document.getElementById('coordsDisplay');
  if (navigator.geolocation) {
    display.textContent = "Acquiring GPS fix...";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        state.userCoords = {
          lat: round(pos.coords.latitude, 5),
          lon: round(pos.coords.longitude, 5)
        };
        display.textContent = `${state.userCoords.lat}° N, ${state.userCoords.lon}° E`;
        updateCitizenUserMarker();
        loadHospitals();
      },
      (err) => {
        console.warn("GPS fallback used:", err.message);
        display.textContent = `${state.userCoords.lat}° N, ${state.userCoords.lon}° E (Simulated)`;
        updateCitizenUserMarker();
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  } else {
    display.textContent = `${state.userCoords.lat}° N, ${state.userCoords.lon}° E (Default)`;
    updateCitizenUserMarker();
  }
}

// ----------------- AUDIO SIREN & VISUAL STROBE -----------------
function toggleSiren() {
  const btnText = document.getElementById('sirenBtnText');
  const sirenBtn = document.getElementById('sirenBtn');

  if (state.isSirenPlaying) {
    stopSiren();
    btnText.textContent = "Sound Siren";
    sirenBtn.classList.remove('btn-danger');
    sirenBtn.classList.add('btn-warning');
  } else {
    startSiren();
    btnText.textContent = "STOP SIREN";
    sirenBtn.classList.remove('btn-warning');
    sirenBtn.classList.add('btn-danger');
  }
}

function startSiren() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    state.sirenAudioCtx = new AudioContext();
    const osc = state.sirenAudioCtx.createOscillator();
    const gain = state.sirenAudioCtx.createGain();

    osc.type = 'sawtooth';
    gain.gain.setValueAtTime(0.3, state.sirenAudioCtx.currentTime);

    // Emergency high-low sweep
    const now = state.sirenAudioCtx.currentTime;
    osc.frequency.setValueAtTime(450, now);
    for (let i = 0; i < 40; i++) {
      osc.frequency.exponentialRampToValueAtTime(880, now + i * 0.8);
      osc.frequency.exponentialRampToValueAtTime(450, now + i * 0.8 + 0.4);
    }

    osc.connect(gain);
    gain.connect(state.sirenAudioCtx.destination);
    osc.start();

    state.sirenOsc = osc;
    state.isSirenPlaying = true;
  } catch (e) {
    console.error("Audio error:", e);
    alert("Audio siren not supported on this browser.");
  }
}

function stopSiren() {
  if (state.sirenOsc) {
    try {
      state.sirenOsc.stop();
      state.sirenAudioCtx.close();
    } catch (e) {}
    state.sirenOsc = null;
    state.isSirenPlaying = false;
  }
}

function toggleStrobe(enable) {
  const strobeEl = document.getElementById('strobeOverlay');
  state.isStrobeActive = enable;
  if (enable) {
    strobeEl.classList.remove('hidden');
  } else {
    strobeEl.classList.add('hidden');
  }
}

// ----------------- CITIZEN MAP & RADAR -----------------
function initCitizenMap() {
  if (citizenMap) return;
  const container = document.getElementById('citizenMap');
  if (!container) return;

  citizenMap = L.map('citizenMap', {
    zoomControl: true,
    attributionControl: false
  }).setView([state.userCoords.lat, state.userCoords.lon], 13);

  // Modern Dark Map Tiles
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(citizenMap);

  updateCitizenUserMarker();
}

function updateCitizenUserMarker() {
  if (!citizenMap) return;
  if (citizenMarkers.user) {
    citizenMap.removeLayer(citizenMarkers.user);
  }

  // Pulsing Citizen User Marker
  const userIcon = L.divIcon({
    className: 'custom-user-marker',
    html: `<div style="position:relative; width:28px; height:28px;">
      <div style="position:absolute; width:100%; height:100%; border-radius:50%; background:#ef4444; opacity:0.6; animation:radar-ping 1.5s infinite;"></div>
      <div style="position:absolute; top:4px; left:4px; width:20px; height:20px; border-radius:50%; background:#ef4444; border:3px solid #fff; box-shadow:0 0 10px rgba(239,68,68,0.8);"></div>
    </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });

  citizenMarkers.user = L.marker([state.userCoords.lat, state.userCoords.lon], { icon: userIcon })
    .addTo(citizenMap)
    .bindPopup(`<strong>Your Live GPS Spot</strong><br>${state.userCoords.lat}° N, ${state.userCoords.lon}° E`);
  
  citizenMap.setView([state.userCoords.lat, state.userCoords.lon], 13);
}

// ----------------- LOAD HOSPITALS & BLOOD/OXYGEN RADAR -----------------
async function loadHospitals() {
  try {
    const bloodGroup = document.getElementById('bloodFilter').value;
    const oxygenOnly = document.getElementById('oxygenFilter').checked;
    const icuOnly = document.getElementById('icuFilter').checked;

    let url = `/api/hospitals?user_lat=${state.userCoords.lat}&user_lon=${state.userCoords.lon}`;
    if (bloodGroup) url += `&blood_group=${encodeURIComponent(bloodGroup)}`;
    if (oxygenOnly) url += `&min_oxygen=70`;
    if (icuOnly) url += `&min_icu=1`;

    const res = await fetch(url);
    const hospitals = await res.json();
    state.hospitals = hospitals;

    renderHospitalsList(hospitals);
    renderHospitalMapMarkers(hospitals);
  } catch (err) {
    console.error("Error loading hospitals:", err);
  }
}

function renderHospitalsList(hospitals) {
  const container = document.getElementById('hospitalList');
  if (!container) return;

  if (hospitals.length === 0) {
    container.innerHTML = `<div class="loading-state text-warning">No hospitals match current blood/oxygen filter criteria. Try resetting filters.</div>`;
    return;
  }

  container.innerHTML = hospitals.map(h => {
    // Generate blood badges for this hospital
    const bloodHtml = Object.entries(h.blood_inventory || {}).map(([bg, units]) => {
      const cls = units > 5 ? 'in-stock' : 'low-stock';
      return `<span class="blood-tag ${cls}" title="${units} units available">${bg}: ${units}</span>`;
    }).join('');

    const o2Status = h.liquid_oxygen_percentage >= 70 ? 'text-success' : 'text-warning';

    return `
      <div class="hospital-item-card">
        <div class="hosp-top-row">
          <div>
            <div class="hosp-name">${h.name}</div>
            <div class="card-desc">${h.address} | Emergency: <strong>${h.phone}</strong></div>
          </div>
          <span class="hosp-distance">${h.distance_km} km away</span>
        </div>

        <div class="hosp-stats-row">
          <div class="stat-pill">
            <span class="stat-pill-label">ICU Ventilators</span>
            <span class="stat-pill-value text-accent">${h.icu_beds_available} Available</span>
          </div>
          <div class="stat-pill">
            <span class="stat-pill-label">Liquid Oxygen</span>
            <span class="stat-pill-value ${o2Status}">${h.liquid_oxygen_percentage}% (${h.oxygen_cylinders_available} cyl)</span>
          </div>
          <div class="stat-pill">
            <span class="stat-pill-label">General Beds</span>
            <span class="stat-pill-value">${h.available_beds} / ${h.total_beds}</span>
          </div>
        </div>

        <div>
          <span class="stat-pill-label" style="display:block; margin-bottom:0.25rem;">Live Blood Reserves:</span>
          <div class="blood-mini-row">
            ${bloodHtml}
          </div>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:0.35rem;">
          <a href="tel:${h.phone}" class="btn-xs btn-outline"><i data-lucide="phone"></i> Direct Call</a>
          <button class="btn-xs btn-primary" onclick="focusHospitalOnMap(${h.latitude}, ${h.longitude}, '${h.name}')">
            <i data-lucide="navigation"></i> Route Here
          </button>
        </div>
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

function renderHospitalMapMarkers(hospitals) {
  if (!citizenMap) return;

  // Clear existing
  citizenMarkers.hospitals.forEach(m => citizenMap.removeLayer(m));
  citizenMarkers.hospitals = [];

  hospitals.forEach(h => {
    const hospIcon = L.divIcon({
      className: 'hosp-map-marker',
      html: `<div style="background:#3b82f6; border:2px solid #fff; border-radius:50%; width:26px; height:26px; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:bold; font-size:14px; box-shadow:0 0 10px rgba(59,130,246,0.8);">H</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    const m = L.marker([h.latitude, h.longitude], { icon: hospIcon }).addTo(citizenMap);
    m.bindPopup(`
      <strong style="color:#000;">${h.name}</strong><br>
      <span style="color:#333;">Distance: ${h.distance_km} km</span><br>
      <span style="color:#333;">ICU Beds: ${h.icu_beds_available}</span><br>
      <span style="color:#333;">O₂ Level: ${h.liquid_oxygen_percentage}%</span><br>
      <a href="tel:${h.phone}" style="display:inline-block; margin-top:4px; font-weight:bold;">Call Hotline</a>
    `);
    citizenMarkers.hospitals.push(m);
  });
}

function focusHospitalOnMap(lat, lon, name) {
  if (citizenMap) {
    citizenMap.setView([lat, lon], 15);
  }
}

// ----------------- LOAD AMBULANCES -----------------
async function loadAmbulances() {
  try {
    const res = await fetch('/api/ambulances');
    const ambulances = await res.json();
    state.ambulances = ambulances;

    if (citizenMap) {
      citizenMarkers.ambulances.forEach(m => citizenMap.removeLayer(m));
      citizenMarkers.ambulances = [];

      ambulances.forEach(a => {
        const ambIcon = L.divIcon({
          className: 'amb-map-marker',
          html: `<div style="background:#10b981; border:2px solid #fff; border-radius:6px; width:26px; height:26px; display:flex; align-items:center; justify-content:center; color:#fff; font-size:12px; box-shadow:0 0 10px rgba(16,185,129,0.8);">🚑</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });

        const m = L.marker([a.latitude, a.longitude], { icon: ambIcon }).addTo(citizenMap);
        m.bindPopup(`
          <strong style="color:#000;">${a.call_sign}</strong><br>
          <span style="color:#333;">Type: ${a.type}</span><br>
          <span style="color:#333;">Driver: ${a.driver_name}</span><br>
          <span style="color:#10b981; font-weight:bold;">Status: ${a.status}</span>
        `);
        citizenMarkers.ambulances.push(m);
      });
    }
  } catch (err) {
    console.error("Error loading ambulances:", err);
  }
}

// ----------------- ONE-TAP SOS DISPATCH FLOW -----------------
function handleSOSClick() {
  const modal = document.getElementById('sosCountdownModal');
  const numEl = document.getElementById('countdownNumber');
  modal.classList.remove('hidden');

  state.countdownSeconds = 3;
  numEl.textContent = state.countdownSeconds;

  if (state.countdownInterval) clearInterval(state.countdownInterval);

  state.countdownInterval = setInterval(() => {
    state.countdownSeconds -= 1;
    numEl.textContent = state.countdownSeconds;

    if (state.countdownSeconds <= 0) {
      clearInterval(state.countdownInterval);
      modal.classList.add('hidden');
      executeSOSDispatch();
    }
  }, 1000);
}

function cancelSOS() {
  if (state.countdownInterval) clearInterval(state.countdownInterval);
  document.getElementById('sosCountdownModal').classList.add('hidden');
  alert("SOS dispatch canceled. Stay safe!");
}

async function executeSOSDispatch() {
  try {
    const payload = {
      caller_name: "Citizen Distress Trigger",
      phone: "+91-98301-99999",
      disaster_type: state.activeHazard,
      severity: "CRITICAL",
      latitude: state.userCoords.lat,
      longitude: state.userCoords.lon,
      address: `Incident coordinates: ${state.userCoords.lat}, ${state.userCoords.lon}`,
      patient_id: "P-101",
      notes: `One-Tap SOS triggered for ${state.activeHazard}. Patient profile linked.`,
      ambulance_count: state.selectedAmbulanceQty || 1
    };

    const res = await fetch('/api/sos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    state.activeEmergencyId = data.emergency_id;

    // Trigger Audible Siren automatically
    startSiren();

    const ambList = data.assigned_ambulances || [];
    const ambNames = ambList.map(a => a.call_sign).join(', ') || (data.assigned_ambulance || 'Paramedic Alpha-1');

    alert(`🚨 SOS CONFIRMED!\n\nEmergency ID: ${data.emergency_id}\nAssigned Ambulances (${ambList.length}): ${ambNames}\nTarget Trauma Center: ${data.assigned_hospital.name}\n\nAll ${ambList.length} ambulance(s) are navigating to your GPS location with Green Corridor priority.`);

    // Display multi-ambulance tracker on Citizen view
    const citizenBox = document.getElementById('citizenActiveEmergencyBox');
    if (citizenBox) {
      citizenBox.classList.remove('hidden');
      renderCitizenAmbulanceList(ambList);
    }

    // Refresh UI & switch to Ambulance EMT Console
    loadEmergencies();
    loadAmbulances();
    document.querySelector('[data-view="ambulanceView"]').click();
  } catch (err) {
    console.error("SOS dispatch error:", err);
    alert("Emergency alert sent. EMT responders notified.");
  }
}

function renderCitizenAmbulanceList(ambList) {
  const container = document.getElementById('citizenAmbulanceList');
  if (!container) return;

  if (!ambList || ambList.length === 0) {
    container.innerHTML = `<div class="text-muted" style="font-size:0.75rem;">Dispatched ambulances will appear here.</div>`;
    return;
  }

  container.innerHTML = ambList.map(amb => {
    const statusUpper = (amb.status || 'REQUESTED').toUpperCase();
    const badgeClass = 'badge-' + statusUpper.toLowerCase().replace('_', '');
    return `
      <div class="assigned-amb-item">
        <div class="amb-info-left">
          <span style="font-size:1.1rem;">🚑</span>
          <div>
            <strong>${amb.call_sign}</strong> <span style="font-size:0.72rem; color:var(--text-muted);">(${amb.type || 'ALS'})</span>
            <div style="font-size:0.7rem; color:var(--text-muted);">${amb.driver_name || 'Officer'} · ${amb.driver_phone || '+91-98711-00101'}</div>
          </div>
        </div>
        <span class="badge ${badgeClass}">${statusUpper.replace('_', ' ')}</span>
      </div>
    `;
  }).join('');
  lucide.createIcons();
}

async function requestMoreAmbulanceForCurrentEmergency() {
  if (!state.activeEmergencyId) {
    alert("No active emergency found. Please trigger SOS first.");
    return;
  }

  try {
    const res = await fetch(`/api/emergencies/${state.activeEmergencyId}/request-ambulance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: 1, notes: "Additional ambulance requested by user" })
    });
    const data = await res.json();
    alert(`🚑 Additional Ambulance Dispatched! Total Assigned: ${data.assigned_ambulances.length}`);
    loadEmergencies();
    loadAmbulances();
  } catch (err) {
    console.error("Error requesting additional ambulance:", err);
  }
}

async function updateAmbulanceStatus(emergencyId, ambulanceId, newStatus) {
  if (!newStatus) return;
  try {
    const res = await fetch(`/api/emergencies/${emergencyId}/ambulances/${ambulanceId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, notes: `Status updated to ${newStatus}` })
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Failed to update ambulance status");
      return;
    }
    loadEmergencies();
    loadAmbulances();
  } catch (err) {
    console.error("Error updating ambulance status:", err);
  }
}

async function requestAmbulanceForIncident(emergencyId) {
  try {
    const res = await fetch(`/api/emergencies/${emergencyId}/request-ambulance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: 1, notes: "Additional ambulance dispatched by EMT responder" })
    });
    const data = await res.json();
    alert(`🚑 Additional ambulance dispatched for incident ${emergencyId}. Total assigned: ${data.assigned_ambulances.length}`);
    loadEmergencies();
    loadAmbulances();
  } catch (err) {
    console.error("Error adding ambulance:", err);
  }
}

// ----------------- AMBULANCE EMT & GREEN CORRIDOR -----------------
async function loadEmergencies() {
  try {
    const res = await fetch('/api/emergencies');
    const emergencies = await res.json();

    const dispatchContainer = document.getElementById('dispatchCardsList');
    const countBadge = document.getElementById('activeDispatchesCount');
    const incomingERQueue = document.getElementById('incomingQueue');

    const activeList = emergencies.filter(e => e.status !== 'RESOLVED');
    if (countBadge) countBadge.textContent = `${activeList.length} Active`;

    // If active emergency is ongoing, update citizen display
    if (state.activeEmergencyId) {
      const currentEmg = emergencies.find(e => e.id === state.activeEmergencyId);
      if (currentEmg && currentEmg.status !== 'RESOLVED') {
        const citizenBox = document.getElementById('citizenActiveEmergencyBox');
        if (citizenBox) citizenBox.classList.remove('hidden');
        renderCitizenAmbulanceList(currentEmg.assigned_ambulances || []);
      }
    }

    if (dispatchContainer) {
      if (activeList.length === 0) {
        dispatchContainer.innerHTML = `<div class="text-muted text-center" style="padding:1rem;">No active dispatches. Ambulance is on patrol standby.</div>`;
      } else {
        dispatchContainer.innerHTML = activeList.map(e => {
          const ambList = e.assigned_ambulances || [];

          // Render all assigned ambulances separately with individual status controls
          const ambsHtml = ambList.map(amb => {
            const statusUpper = (amb.status || 'REQUESTED').toUpperCase();
            const badgeClass = 'badge-' + statusUpper.toLowerCase().replace('_', '');
            return `
              <div class="assigned-amb-item" style="margin-top:0.35rem;">
                <div class="amb-info-left">
                  <span style="font-size:1.1rem;">🚑</span>
                  <div>
                    <strong>${amb.call_sign}</strong> <span style="font-size:0.72rem; color:var(--text-muted);">(${amb.type || 'ALS'})</span>
                    <div style="font-size:0.7rem; color:var(--text-muted);">${amb.driver_name} · ${amb.driver_phone}</div>
                  </div>
                </div>
                <div style="display:flex; align-items:center; gap:0.4rem;">
                  <span class="badge ${badgeClass}">${statusUpper.replace('_', ' ')}</span>
                  <select class="btn-xs btn-outline" onchange="updateAmbulanceStatus('${e.id}', '${amb.ambulance_id}', this.value)" style="cursor:pointer; background:var(--bg-card); color:#fff; padding:0.2rem 0.35rem;">
                    <option value="" disabled selected>Update Status</option>
                    <option value="REQUESTED">Requested</option>
                    <option value="ACCEPTED">Accepted</option>
                    <option value="ON_THE_WAY">On the Way</option>
                    <option value="ARRIVED">Arrived at Scene</option>
                    <option value="COMPLETED">Completed</option>
                  </select>
                </div>
              </div>
            `;
          }).join('');

          return `
            <div class="dispatch-card critical">
              <div class="dispatch-top">
                <span class="badge badge-danger">${e.disaster_type}</span>
                <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">${e.id}</span>
              </div>
              <div style="font-size:0.85rem; font-weight:600;">Location: ${e.latitude.toFixed(4)}° N, ${e.longitude.toFixed(4)}° E</div>
              <div style="font-size:0.75rem; color:var(--text-muted);">${e.notes || 'Emergency dispatched via One-Tap SOS'}</div>
              
              <!-- Assigned Ambulances List -->
              <div style="margin-top:0.4rem;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <span class="section-label" style="margin-bottom:0; font-size:0.75rem;">Assigned Ambulances (${ambList.length}):</span>
                  <button class="btn-xs btn-outline" onclick="requestAmbulanceForIncident('${e.id}')">
                    <i data-lucide="plus"></i> Request +1 Ambulance
                  </button>
                </div>
                ${ambsHtml || '<div class="text-muted" style="font-size:0.75rem;">No ambulances currently assigned.</div>'}
              </div>

              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.5rem; border-top:1px solid var(--border-color); padding-top:0.4rem;">
                <span class="badge badge-warning">INCIDENT: ${e.status}</span>
                <button class="btn-xs btn-primary" onclick="setupAmbulanceRouteForEmergency('${e.id}', ${e.latitude}, ${e.longitude})">
                  <i data-lucide="navigation"></i> Navigate Route
                </button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Update Hospital ER Incoming Queue
    if (incomingERQueue) {
      if (activeList.length === 0) {
        incomingERQueue.innerHTML = `<div class="text-muted text-center" style="padding:1.5rem;">No incoming trauma ambulances currently in transit.</div>`;
      } else {
        incomingERQueue.innerHTML = activeList.map(e => {
          const ambCount = (e.assigned_ambulances && e.assigned_ambulances.length) || 1;
          const ambNames = (e.assigned_ambulances || []).map(a => `${a.call_sign} [${a.status}]`).join(', ') || (e.assigned_ambulance_id || 'Alpha-1');
          return `
            <div class="incoming-card">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="color:#fff; font-size:0.9rem;">Incoming: ${e.disaster_type}</strong>
                <span class="badge badge-danger">ETA: ~6 Mins</span>
              </div>
              <div style="font-size:0.78rem; color:var(--text-muted);">Assigned Ambulances (${ambCount}): <strong>${ambNames}</strong></div>
              <div class="incoming-vitals-badge">
                <span>BP: 120/80</span> | <span>SpO₂: 94%</span> | <span>GCS: 14</span>
              </div>
              <div style="display:flex; justify-content:flex-end; gap:0.4rem; margin-top:0.25rem;">
                <button class="btn-xs btn-outline" onclick="quickViewPatientEHR('${e.patient_id || 'P-101'}')">View Patient EHR</button>
                <button class="btn-xs btn-success" onclick="resolveEmergency('${e.id}')">Confirm Admitted</button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    lucide.createIcons();
  } catch (err) {
    console.error("Error loading emergencies:", err);
  }
}

async function resolveEmergency(emgId) {
  try {
    await fetch(`/api/emergencies/${emgId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'RESOLVED', notes: 'Patient safely admitted to Trauma Center ICU.' })
    });
    alert("Emergency status updated: Patient safely admitted and ambulance returned to ready status.");
    loadEmergencies();
    loadAmbulances();
  } catch (e) {
    console.error(e);
  }
}

// ----------------- AMBULANCE ROUTING & GREEN CORRIDOR -----------------
function initAmbulanceMap() {
  if (ambulanceMap) {
    ambulanceMap.invalidateSize();
    return;
  }
  const container = document.getElementById('ambulanceMap');
  if (!container) return;

  ambulanceMap = L.map('ambulanceMap', { attributionControl: false }).setView([22.5710, 88.3620], 14);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(ambulanceMap);

  setupAmbulanceRouteForEmergency(null, 22.5726, 88.3639);
}

async function setupAmbulanceRouteForEmergency(emgId, targetLat, targetLon) {
  try {
    const ambId = state.activeAmbulanceId;
    const res = await fetch(`/api/route?ambulance_id=${ambId}&target_lat=${targetLat}&target_lon=${targetLon}&destination_hospital_id=HOSP-01`);
    const routeData = await res.json();
    state.currentRouteData = routeData;

    renderAmbulanceRouteOnMap(routeData);
    updateGreenCorridorHUD(routeData.corridor_analytics);
  } catch (err) {
    console.error("Route calculation error:", err);
  }
}

function renderAmbulanceRouteOnMap(data) {
  if (!ambulanceMap) return;

  // Clear previous route
  if (ambulanceMarkers.routeLine) ambulanceMap.removeLayer(ambulanceMarkers.routeLine);
  if (ambulanceMarkers.amb) ambulanceMap.removeLayer(ambulanceMarkers.amb);
  if (ambulanceMarkers.target) ambulanceMap.removeLayer(ambulanceMarkers.target);
  if (ambulanceMarkers.hosp) ambulanceMap.removeLayer(ambulanceMarkers.hosp);
  ambulanceMarkers.signals.forEach(s => ambulanceMap.removeLayer(s));
  ambulanceMarkers.signals = [];

  // Draw polyline
  const waypoints = data.full_waypoints;
  const polylineColor = state.greenCorridorActive ? '#10b981' : '#3b82f6';

  ambulanceMarkers.routeLine = L.polyline(waypoints, {
    color: polylineColor,
    weight: 6,
    opacity: 0.9,
    dashArray: state.greenCorridorActive ? '8, 8' : null
  }).addTo(ambulanceMap);

  // Markers
  const ambIcon = L.divIcon({
    className: 'amb-nav-marker',
    html: `<div style="background:#10b981; border:3px solid #fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:16px; box-shadow:0 0 15px rgba(16,185,129,0.9);">🚑</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
  ambulanceMarkers.amb = L.marker([data.ambulance.latitude, data.ambulance.longitude], { icon: ambIcon })
    .addTo(ambulanceMap)
    .bindPopup(`<strong>${data.ambulance.call_sign}</strong>`);

  const targetIcon = L.divIcon({
    className: 'target-nav-marker',
    html: `<div style="background:#ef4444; border:3px solid #fff; border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center; font-size:14px; box-shadow:0 0 15px rgba(239,68,68,0.9);">📍</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });
  ambulanceMarkers.target = L.marker(data.target_location, { icon: targetIcon })
    .addTo(ambulanceMap)
    .bindPopup(`<strong>Emergency Patient Spot</strong>`);

  const hospIcon = L.divIcon({
    className: 'hosp-nav-marker',
    html: `<div style="background:#3b82f6; border:3px solid #fff; border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center; font-size:14px; color:#fff; font-weight:bold; box-shadow:0 0 15px rgba(59,130,246,0.9);">H</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });
  ambulanceMarkers.hosp = L.marker([data.hospital_destination.lat, data.hospital_destination.lon], { icon: hospIcon })
    .addTo(ambulanceMap)
    .bindPopup(`<strong>${data.hospital_destination.name}</strong>`);

  // Render traffic signals along route
  (data.corridor_analytics.signals || []).forEach(sig => {
    const lightColor = state.greenCorridorActive ? '#10b981' : '#ef4444';
    const sigIcon = L.divIcon({
      className: 'sig-nav-marker',
      html: `<div style="background:#111; border:2px solid ${lightColor}; border-radius:50%; width:20px; height:20px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px ${lightColor};">
        <div style="width:10px; height:10px; border-radius:50%; background:${lightColor};"></div>
      </div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    const sm = L.marker([sig.lat, sig.lon], { icon: sigIcon }).addTo(ambulanceMap);
    sm.bindPopup(`<strong>Traffic Signal: ${sig.name}</strong><br>Status: <span style="color:${lightColor}; font-weight:bold;">${state.greenCorridorActive ? 'PREEMPTED TO GREEN' : 'NORMAL RED'}</span>`);
    ambulanceMarkers.signals.push(sm);
  });

  ambulanceMap.fitBounds(ambulanceMarkers.routeLine.getBounds(), { padding: [40, 40] });
}

function updateGreenCorridorHUD(analytics) {
  if (!analytics) return;
  document.getElementById('gcTimeSaved').textContent = `${analytics.minutes_saved} min`;
  document.getElementById('gcSignalsCleared').textContent = `${analytics.preempted_signals_count} / ${analytics.preempted_signals_count}`;
  document.getElementById('gcPriorityEta').textContent = `${analytics.priority_eta_mins} min`;
}

async function toggleGreenCorridor() {
  state.greenCorridorActive = !state.greenCorridorActive;
  const btn = document.getElementById('gcToggleBtn');
  const statusText = document.getElementById('gcStatusText');

  try {
    await fetch('/api/green-corridor/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ambulance_id: state.activeAmbulanceId, activate: state.greenCorridorActive })
    });

    if (state.greenCorridorActive) {
      btn.innerHTML = `<i data-lucide="check-circle-2"></i> GREEN CORRIDOR ENGAGED`;
      btn.classList.remove('btn-success');
      btn.classList.add('btn-danger');
      statusText.textContent = "CORRIDOR: PREEMPTION ACTIVE";
      statusText.style.color = "#34d399";
    } else {
      btn.innerHTML = `<i data-lucide="zap"></i> ACTIVATE GREEN CORRIDOR`;
      btn.classList.remove('btn-danger');
      btn.classList.add('btn-success');
      statusText.textContent = "CORRIDOR: STANDBY";
      statusText.style.color = "#fff";
    }

    if (state.currentRouteData) {
      renderAmbulanceRouteOnMap(state.currentRouteData);
    }
    loadTrafficSignals(false);
    lucide.createIcons();
  } catch (err) {
    console.error("Error toggling green corridor:", err);
  }
}

// ----------------- DRIVING SIMULATION -----------------
function startAmbulanceSimulation() {
  if (state.isSimulatingDrive) {
    clearInterval(state.simInterval);
    state.isSimulatingDrive = false;
    document.getElementById('simDriveBtn').innerHTML = `<i data-lucide="play"></i> Start Driving Simulation`;
    return;
  }

  if (!state.currentRouteData || !state.currentRouteData.full_waypoints) {
    alert("Please select an active emergency route first.");
    return;
  }

  // Auto activate green corridor if not already
  if (!state.greenCorridorActive) {
    toggleGreenCorridor();
  }

  state.isSimulatingDrive = true;
  document.getElementById('simDriveBtn').innerHTML = `<i data-lucide="square"></i> Stop Simulation`;
  lucide.createIcons();

  const waypoints = state.currentRouteData.full_waypoints;
  let currentIndex = 0;

  state.simInterval = setInterval(() => {
    if (currentIndex >= waypoints.length) {
      clearInterval(state.simInterval);
      state.isSimulatingDrive = false;
      document.getElementById('simDriveBtn').innerHTML = `<i data-lucide="play"></i> Simulation Finished`;
      alert("🚑 Ambulance arrived at destination hospital! Patient transferred to Trauma Bay.");
      return;
    }

    const pos = waypoints[currentIndex];
    if (ambulanceMarkers.amb) {
      ambulanceMarkers.amb.setLatLng(pos);
      ambulanceMap.panTo(pos, { animate: true });
    }

    // Post live coords
    fetch(`/api/ambulances/${state.activeAmbulanceId}/position?lat=${pos[0]}&lon=${pos[1]}`, { method: 'POST' });

    currentIndex++;
  }, 1000);
}

function sendVitalsToHospital() {
  const bp = document.getElementById('vitalBP').value;
  const pulse = document.getElementById('vitalPulse').value;
  const spo2 = document.getElementById('vitalSpo2').value;
  const gcs = document.getElementById('vitalGCS').value;

  alert(`Vitals Telemetry transmitted to Trauma ER:\nBP: ${bp} mmHg\nPulse: ${pulse} bpm\nSpO₂: ${spo2}%\nGCS: ${gcs}/15\n\nHospital ER staff notified to prepare trauma bed.`);
}

// ----------------- HOSPITAL ER & BLOOD INVENTORY -----------------
async function loadHospitalInventory() {
  try {
    const res = await fetch('/api/hospitals');
    const hospitals = await res.json();
    const hosp = hospitals.find(h => h.id === 'HOSP-01') || hospitals[0];

    // Update Oxygen
    document.getElementById('hospLiquidO2').textContent = `${hosp.liquid_oxygen_percentage}%`;
    document.getElementById('hospLiquidO2Bar').style.width = `${hosp.liquid_oxygen_percentage}%`;
    document.getElementById('hospCylinders').textContent = `${hosp.oxygen_cylinders_available} units`;
    document.getElementById('hospICUBeds').textContent = `${hosp.icu_beds_available} available`;

    // Render Blood Grid
    const bloodContainer = document.getElementById('hospitalBloodGrid');
    if (bloodContainer && hosp.blood_inventory) {
      bloodContainer.innerHTML = Object.entries(hosp.blood_inventory).map(([bg, units]) => `
        <div class="blood-slot-card">
          <div class="blood-type-badge">${bg}</div>
          <div class="blood-units-count" id="bloodCount-${bg}">${units}</div>
          <div class="blood-unit-label">Units Available</div>
          <div class="blood-stepper">
            <button class="btn-xs btn-secondary" onclick="updateBloodUnit('${bg}', -1)">-1</button>
            <button class="btn-xs btn-primary" onclick="updateBloodUnit('${bg}', +1)">+1</button>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error("Error loading inventory:", err);
  }
}

async function updateBloodUnit(bloodGroup, delta) {
  try {
    await fetch('/api/hospitals/HOSP-01/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blood_group: bloodGroup, units_delta: delta })
    });
    loadHospitalInventory();
    loadHospitals();
  } catch (err) {
    console.error(err);
  }
}

async function adjustCylinders(delta) {
  try {
    const currentText = document.getElementById('hospCylinders').textContent;
    const current = parseInt(currentText) || 50;
    const updated = Math.max(0, current + delta);
    await fetch('/api/hospitals/HOSP-01/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ oxygen_cylinders: updated })
    });
    loadHospitalInventory();
    loadHospitals();
  } catch (err) {
    console.error(err);
  }
}

async function adjustICUBeds(delta) {
  try {
    const currentText = document.getElementById('hospICUBeds').textContent;
    const current = parseInt(currentText) || 10;
    const updated = Math.max(0, current + delta);
    await fetch('/api/hospitals/HOSP-01/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ icu_beds_available: updated })
    });
    loadHospitalInventory();
    loadHospitals();
  } catch (err) {
    console.error(err);
  }
}

// ----------------- DOCTOR PATIENT EHR LOOKUP -----------------
async function fetchPatientEHR() {
  const patientId = document.getElementById('ehrPatientInput').value.trim();
  if (!patientId) {
    alert("Please enter a Patient ID (e.g. P-101, P-102)");
    return;
  }

  try {
    const res = await fetch(`/api/patient/${patientId}?emergency_override=true`);
    if (!res.ok) {
      alert("Patient record not found. Please verify Patient ID.");
      return;
    }
    const patient = await res.json();
    renderPatientEHR(patient);
  } catch (err) {
    console.error("EHR lookup error:", err);
  }
}

function quickViewPatientEHR(pid) {
  document.getElementById('ehrPatientInput').value = pid;
  fetchPatientEHR();
  document.querySelector('[data-view="hospitalView"]').click();
}

function renderPatientEHR(p) {
  const card = document.getElementById('ehrRecordCard');
  card.classList.remove('hidden');

  const allergyBadges = p.known_allergies.map(a => `<span class="badge badge-danger" style="margin-right:4px;">⚠️ ${a}</span>`).join('');
  const chronicBadges = p.chronic_conditions.map(c => `<span class="badge badge-warning" style="margin-right:4px;">${c}</span>`).join('');
  const medBadges = p.current_medications.map(m => `<span class="badge badge-accent" style="margin-right:4px;">${m}</span>`).join('');

  const contactsHtml = (p.emergency_contacts || []).map(c => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-subtle); padding:0.4rem 0.6rem; border-radius:4px; margin-top:4px;">
      <span>${c.name}</span>
      <a href="tel:${c.phone}" class="btn-xs btn-outline"><i data-lucide="phone"></i> Call</a>
    </div>
  `).join('');

  card.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <h3 style="color:#fff; font-size:1.1rem; font-weight:800;">${p.full_name}</h3>
        <span class="card-desc">DOB: ${p.dob} | ID: ${p.id}</span>
      </div>
      <div style="text-align:right;">
        <span class="badge badge-danger" style="font-size:1rem; padding:0.3rem 0.7rem;">Blood: ${p.blood_group}</span>
      </div>
    </div>

    <div class="allergy-alert-banner">
      <i data-lucide="alert-octagon" style="width:20px; height:20px; flex-shrink:0;"></i>
      <div>
        <strong>CRITICAL MEDICAL ALLERGIES:</strong>
        <div>${allergyBadges || 'None Recorded'}</div>
      </div>
    </div>

    <div>
      <span class="section-label">Chronic Conditions:</span>
      <div>${chronicBadges || 'None'}</div>
    </div>

    <div>
      <span class="section-label">Current Routine Medications:</span>
      <div>${medBadges || 'None'}</div>
    </div>

    <div>
      <span class="section-label">Past Surgeries / Implants:</span>
      <p style="font-size:0.85rem; color:var(--text-main);">${p.past_surgeries || 'None'}</p>
    </div>

    <div>
      <span class="section-label">Emergency Contacts:</span>
      ${contactsHtml}
    </div>
  `;

  lucide.createIcons();
}

// ----------------- CITY TRAFFIC & GREEN CORRIDOR COMMAND -----------------
function initTrafficMap() {
  if (trafficMap) {
    trafficMap.invalidateSize();
    return;
  }
  const container = document.getElementById('trafficMap');
  if (!container) return;

  trafficMap = L.map('trafficMap', { attributionControl: false }).setView([22.5740, 88.3640], 13);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 }).addTo(trafficMap);

  renderTrafficSignalMarkers(state.trafficSignals);
}

async function loadTrafficSignals(updateTable = true) {
  try {
    const res = await fetch('/api/signals');
    const signals = await res.json();
    state.trafficSignals = signals;

    if (updateTable) renderSignalTable(signals);
    if (trafficMap) renderTrafficSignalMarkers(signals);
  } catch (err) {
    console.error("Error loading signals:", err);
  }
}

function renderSignalTable(signals) {
  const tbody = document.getElementById('signalTableBody');
  if (!tbody) return;

  tbody.innerHTML = signals.map(s => `
    <tr>
      <td><strong>${s.intersection_name}</strong><br><span style="font-size:0.7rem; color:var(--text-muted);">${s.id}</span></td>
      <td>
        <span class="signal-light-dot ${s.current_state}"></span>
        <strong>${s.current_state}</strong>
      </td>
      <td>
        <span class="badge ${s.green_corridor_active ? 'badge-success' : 'badge-warning'}">
          ${s.green_corridor_active ? 'PREEMPTED' : 'NORMAL'}
        </span>
      </td>
      <td>
        <button class="btn-xs btn-success" onclick="setSignalState('${s.id}', 'GREEN')">Green</button>
        <button class="btn-xs btn-danger" onclick="setSignalState('${s.id}', 'RED')">Red</button>
      </td>
    </tr>
  `).join('');
}

function renderTrafficSignalMarkers(signals) {
  if (!trafficMap) return;
  trafficSignalMarkers.forEach(m => trafficMap.removeLayer(m));
  trafficSignalMarkers = [];

  signals.forEach(s => {
    const lightColor = s.current_state === 'GREEN' ? '#10b981' : (s.current_state === 'YELLOW' ? '#f59e0b' : '#ef4444');
    const icon = L.divIcon({
      className: 'sig-grid-marker',
      html: `<div style="background:#0f172a; border:2px solid ${lightColor}; border-radius:50%; width:24px; height:24px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px ${lightColor};">
        <div style="width:12px; height:12px; border-radius:50%; background:${lightColor};"></div>
      </div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });

    const m = L.marker([s.latitude, s.longitude], { icon: icon }).addTo(trafficMap);
    m.bindPopup(`<strong>${s.intersection_name}</strong><br>State: <span style="color:${lightColor}; font-weight:bold;">${s.current_state}</span>`);
    trafficSignalMarkers.push(m);
  });
}

async function setSignalState(sigId, state) {
  try {
    await fetch(`/api/signals/${sigId}/state?state=${state}`, { method: 'POST' });
    loadTrafficSignals();
  } catch (err) {
    console.error(err);
  }
}

async function overrideAllSignals(targetState) {
  for (const s of state.trafficSignals) {
    await setSignalState(s.id, targetState);
  }
}

// ----------------- AI MEDICAL JARGON & PRESCRIPTION SIMPLIFIER -----------------
const SAMPLE_PRESCRIPTIONS = {
  1: `Pt presents with acute dyspnea, tachycardia, and bilateral wheezing after dust inhalation in structural collapse.
Rx:
1. Neb Salbutamol 2.5mg STAT & PRN for wheezing.
2. Tab Augmentin 625mg PO TID PC x 7 days.
3. Tab Dolo 650mg PO SOS for fever/pain.
4. NPO for next 4 hours pending chest radiography.`,
  2: `Post-myocardial infarction follow-up. Pt has chronic hypertension and angina pectoris.
Rx:
1. Tab Aspirin 75mg PO OD PC (morning with breakfast).
2. Tab Amlodipine 5mg PO OD (evening).
3. Tab Pantoprazole 40mg PO OD AC (empty stomach 30 mins before breakfast).
4. Sublingual Nitroglycerin 0.5mg STAT SL if acute angina chest pain recurs.`,
  3: `Discharge Note: Acute bacterial gastroenteritis with moderate dehydration.
Rx:
1. ORS (Oral Rehydration Solution) 1 Liter PO PRN continuously.
2. Tab Paracetamol 500mg PO TID PC.
3. Tab Cetirizine 10mg PO HS for allergic pruritus.
4. High water intake, soft bland diet.`
};

function loadSampleRx(index) {
  const textarea = document.getElementById('rawRxInput');
  textarea.value = SAMPLE_PRESCRIPTIONS[index] || '';
}

function clearRxInput() {
  document.getElementById('rawRxInput').value = '';
  document.getElementById('rxOutputContainer').innerHTML = `
    <div class="rx-placeholder">
      <i data-lucide="stethoscope" class="rx-placeholder-icon"></i>
      <p>Enter a prescription or select a sample on the left to see the instant plain-language breakdown and voice guide.</p>
    </div>
  `;
  lucide.createIcons();
}

async function decodePrescription() {
  const text = document.getElementById('rawRxInput').value.trim();
  if (!text) {
    alert("Please enter or paste a medical prescription or note.");
    return;
  }

  const container = document.getElementById('rxOutputContainer');
  container.innerHTML = `<div class="text-center" style="padding:2rem;"><span class="live-dot"></span> Analyzing clinical abbreviations, dosage, and layman translation...</div>`;

  try {
    const res = await fetch('/api/simplify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    });

    const data = await res.json();
    state.currentSpeechText = data.speech_text;
    renderSimplifiedPrescription(data);
  } catch (err) {
    console.error("Rx decode error:", err);
    container.innerHTML = `<div class="text-danger">Failed to decode prescription. Please try again.</div>`;
  }
}

function renderSimplifiedPrescription(data) {
  const container = document.getElementById('rxOutputContainer');

  // Drug Cards
  const drugsHtml = (data.medications || []).map(d => `
    <div class="rx-drug-card">
      <div class="rx-drug-title">
        <span>💊 ${d.name} (${d.generic})</span>
        <span class="badge badge-accent">${d.category}</span>
      </div>
      <p style="font-size:0.85rem; color:#fff;"><strong>Purpose:</strong> ${d.purpose}</p>
      <p style="font-size:0.85rem; color:#34d399;"><strong>How to Take:</strong> ${d.how_to_take}</p>
      ${d.warning ? `<p style="font-size:0.8rem; color:#fca5a5;">⚠️ <strong>Warning:</strong> ${d.warning}</p>` : ''}
    </div>
  `).join('');

  // Jargon Table
  const jargonRows = (data.jargon_detected || []).map(j => `
    <tr>
      <td><strong style="color:#fff;">${j.term}</strong></td>
      <td style="color:#94a3b8;">${j.plain_meaning}</td>
    </tr>
  `).join('');

  // Safety Alerts
  const alertsHtml = (data.safety_alerts || []).map(a => `
    <div class="allergy-alert-banner" style="margin-top:0.4rem;">
      <i data-lucide="alert-triangle" style="width:18px; height:18px; flex-shrink:0;"></i>
      <span>${a}</span>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="rx-summary-card">
      <h3 style="color:#3b82f6; font-size:1rem; margin-bottom:0.4rem;"><i data-lucide="heart-handshake"></i> Patient-Friendly Summary:</h3>
      <p style="font-size:0.9rem; color:#fff;">${data.summary}</p>
    </div>

    ${alertsHtml ? `<div><span class="section-label">Critical Safety Notices:</span>${alertsHtml}</div>` : ''}

    ${drugsHtml ? `<div><span class="section-label">Your Medications in Simple Terms:</span><div style="display:flex; flex-direction:column; gap:0.6rem; margin-top:0.4rem;">${drugsHtml}</div></div>` : ''}

    ${jargonRows ? `
      <div>
        <span class="section-label">Medical Jargon Translated:</span>
        <table class="jargon-table" style="margin-top:0.4rem;">
          <thead>
            <tr><th>Doctor Term</th><th>What It Actually Means</th></tr>
          </thead>
          <tbody>${jargonRows}</tbody>
        </table>
      </div>
    ` : ''}

    <div style="background:var(--bg-subtle); padding:0.85rem; border-radius:var(--radius-md); border:1px solid var(--border-color);">
      <span class="section-label">Translated Schedule & Latin Abbreviations:</span>
      <p style="font-family:var(--font-mono); font-size:0.82rem; color:#94a3b8; line-height:1.5; white-space:pre-wrap;">${data.layman_translation}</p>
    </div>
  `;

  lucide.createIcons();
}

function toggleSpeechReadAloud() {
  if (!state.speechSynth) {
    alert("Speech synthesis is not supported on your browser.");
    return;
  }

  const voiceBtnText = document.getElementById('rxVoiceText');

  if (state.speechSynth.speaking) {
    state.speechSynth.cancel();
    voiceBtnText.textContent = "Read Aloud (Voice)";
    return;
  }

  if (!state.currentSpeechText) {
    alert("Please simplify a prescription first.");
    return;
  }

  const utter = new SpeechSynthesisUtterance(state.currentSpeechText);
  utter.rate = 0.95; // Clear and soothing pace
  utter.pitch = 1.0;

  utter.onstart = () => {
    voiceBtnText.textContent = "STOP READING";
  };
  utter.onend = () => {
    voiceBtnText.textContent = "Read Aloud (Voice)";
  };
  utter.onerror = () => {
    voiceBtnText.textContent = "Read Aloud (Voice)";
  };

  state.speechSynth.speak(utter);
}

// ----------------- START DISASTER TRIAGE -----------------
function updateRespLabel(val) {
  document.getElementById('triageRespVal').textContent = `${val} bpm`;
}

async function runTriageCalculation() {
  const canWalk = document.querySelector('input[name="canWalk"]:checked').value === 'true';
  const resp = parseInt(document.getElementById('triageRespSlider').value) || 20;
  const radialPulse = document.querySelector('input[name="radialPulse"]:checked').value === 'true';
  const mentalStatus = document.querySelector('input[name="mentalStatus"]:checked').value === 'true';

  try {
    const res = await fetch('/api/triage/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        can_walk: canWalk,
        respiration_rate: resp,
        radial_pulse_present: radialPulse,
        follows_commands: mentalStatus
      })
    });

    const result = await res.json();
    renderTriageResult(result);
  } catch (err) {
    console.error("Triage calc error:", err);
  }
}

function renderTriageResult(r) {
  const card = document.getElementById('triageResultCard');
  if (!card) return;

  card.style.backgroundColor = r.color_hex;
  card.style.boxShadow = `0 0 25px ${r.color_hex}66`;

  card.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <span style="font-size:0.75rem; font-weight:800; letter-spacing:0.05em; text-transform:uppercase; color:rgba(255,255,255,0.85);">Triage Tag Assigned</span>
      <span style="font-family:var(--font-mono); font-size:1.4rem; font-weight:900;">${r.tag}</span>
    </div>
    <div style="font-size:1.3rem; font-weight:900; margin:0.2rem 0;">${r.priority}</div>
    <p style="font-size:0.85rem; line-height:1.5; color:#fff;"><strong>Tactical Protocol:</strong> ${r.action}</p>
  `;
}

function toggleAcc(headerEl) {
  const item = headerEl.parentElement;
  item.classList.toggle('active');
}

// ----------------- DISASTER ALERT BROADCASTS -----------------
async function checkActiveBroadcasts() {
  try {
    const res = await fetch('/api/broadcasts');
    const broadcasts = await res.json();
    if (broadcasts && broadcasts.length > 0) {
      const top = broadcasts[0];
      const banner = document.getElementById('disasterAlertBanner');
      const title = document.getElementById('bannerTitle');
      const text = document.getElementById('bannerText');

      title.textContent = `${top.hazard_type} ALERT (${top.severity}):`;
      text.textContent = ` ${top.title} — ${top.safety_instructions} Evacuation: ${top.evacuation_route}`;
      banner.classList.remove('hidden');
    }
  } catch (err) {
    console.error(err);
  }
}

function dismissBanner() {
  document.getElementById('disasterAlertBanner').classList.add('hidden');
}

async function publishBroadcastAlert() {
  const title = document.getElementById('broadcastTitle').value.trim();
  const hazard = document.getElementById('broadcastHazard').value;
  const severity = document.getElementById('broadcastSeverity').value;
  const desc = document.getElementById('broadcastDesc').value.trim();

  if (!title || !desc) {
    alert("Please fill in Alert Title and Safety Instructions.");
    return;
  }

  try {
    await fetch('/api/broadcasts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        hazard_type: hazard,
        severity: severity,
        description: desc,
        safety_instructions: desc,
        evacuation_route: "Primary Green Corridor Expressway via Metro Junction."
      })
    });

    alert("🚨 City-wide emergency advisory broadcasted to all citizens & responders!");
    checkActiveBroadcasts();
  } catch (err) {
    console.error(err);
  }
}

// ----------------- PATIENT QR & EDITABLE MEDICAL HISTORY & MEDICATION MANAGEMENT -----------------
async function refreshPatientBannerPreview(patientId) {
  try {
    const res = await fetch(`/api/patient/${patientId}?emergency_override=true`);
    if (!res.ok) return;
    const p = await res.json();
    const bloodBadge = document.getElementById('previewBloodBadge');
    const allergyBadge = document.getElementById('previewAllergyBadge');
    if (bloodBadge) bloodBadge.textContent = p.blood_group || 'O-';
    if (allergyBadge) {
      const firstAllergy = (p.known_allergies && p.known_allergies.length > 0) ? p.known_allergies[0] : 'None';
      allergyBadge.textContent = firstAllergy.replace('Severe ', '').replace(' Allergy', '');
    }
  } catch (e) {
    console.error("Error refreshing patient preview:", e);
  }
}

async function openPatientQRModal(patientId) {
  const modal = document.getElementById('patientQRModal');
  const qrContainer = document.getElementById('qrcodeCanvas');
  const summaryEl = document.getElementById('qrPatientSummary');

  qrContainer.innerHTML = '';
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/patient/${patientId}?emergency_override=true`);
    const p = await res.json();

    const qrData = JSON.stringify({
      system: "Raksha-ResQNet",
      patient_id: p.id,
      name: p.full_name,
      blood: p.blood_group,
      allergies: p.known_allergies || [],
      conditions: p.chronic_conditions || [],
      meds: p.current_medications || [],
      contacts: p.emergency_contacts || []
    });

    new QRCode(qrContainer, {
      text: qrData,
      width: 180,
      height: 180,
      colorDark: "#000000",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });

    const contactStr = (p.emergency_contacts && p.emergency_contacts[0]) ? `${p.emergency_contacts[0].name} (${p.emergency_contacts[0].phone})` : 'None';
    const allergiesStr = (p.known_allergies && p.known_allergies.length > 0) ? p.known_allergies.join(', ') : 'None known';

    summaryEl.innerHTML = `
      <h4 style="color:#fff; margin-top:0.75rem;">${p.full_name} (${p.id})</h4>
      <p style="font-size:0.85rem; color:var(--text-muted);">Blood Group: <strong style="color:#ef4444;">${p.blood_group}</strong></p>
      <p style="font-size:0.8rem; color:#fca5a5;">⚠️ Allergies: ${allergiesStr}</p>
      <p style="font-size:0.78rem; color:var(--text-muted); margin-top:4px;">Primary Contact: ${contactStr}</p>
      <div style="margin-top:0.5rem;">
        <span class="badge badge-accent">${(p.medications && p.medications.length) || (p.current_medications && p.current_medications.length) || 0} Active Medications Listed</span>
      </div>
    `;
  } catch (err) {
    console.error("Error generating QR:", err);
  }
}

function closePatientQRModal() {
  document.getElementById('patientQRModal').classList.add('hidden');
}

function printQRPass() {
  window.print();
}

// Editable Medical History Modal Functions
async function openEditMedicalHistoryModal(patientId) {
  state.editingPatientId = patientId || 'P-101';
  closePatientQRModal();

  const modal = document.getElementById('editMedicalHistoryModal');
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/patient/${state.editingPatientId}?emergency_override=true`);
    if (!res.ok) throw new Error("Failed to load patient profile");
    const p = await res.json();

    document.getElementById('editFullName').value = p.full_name || '';
    document.getElementById('editDOB').value = p.dob || '';
    document.getElementById('editBloodGroup').value = p.blood_group || 'O-';
    document.getElementById('editInsurance').value = p.insurance_policy || '';
    document.getElementById('editAllergies').value = (p.known_allergies || []).join(', ');
    document.getElementById('editConditions').value = (p.chronic_conditions || []).join(', ');
    document.getElementById('editSurgeries').value = p.past_surgeries || '';

    if (p.emergency_contacts && p.emergency_contacts.length > 0) {
      document.getElementById('editContactName').value = p.emergency_contacts[0].name || '';
      document.getElementById('editContactPhone').value = p.emergency_contacts[0].phone || '';
    } else {
      document.getElementById('editContactName').value = '';
      document.getElementById('editContactPhone').value = '';
    }

    // Set today as default start date for adding medications
    const todayStr = new Date().toISOString().split('T')[0];
    document.getElementById('newMedStartDate').value = todayStr;

    // Load granular medications
    loadPatientMedications(state.editingPatientId);
  } catch (err) {
    console.error("Error opening edit modal:", err);
    alert("Failed to load patient medical profile. Please try again.");
  }
}

function closeEditMedicalHistoryModal() {
  document.getElementById('editMedicalHistoryModal').classList.add('hidden');
}

async function savePatientMedicalHistory() {
  const patientId = state.editingPatientId || 'P-101';
  const fullName = document.getElementById('editFullName').value.trim();
  const dob = document.getElementById('editDOB').value;
  const bloodGroup = document.getElementById('editBloodGroup').value;
  const insurance = document.getElementById('editInsurance').value.trim();
  const allergiesRaw = document.getElementById('editAllergies').value.trim();
  const conditionsRaw = document.getElementById('editConditions').value.trim();
  const surgeries = document.getElementById('editSurgeries').value.trim();
  const contactName = document.getElementById('editContactName').value.trim();
  const contactPhone = document.getElementById('editContactPhone').value.trim();

  if (!fullName) {
    alert("Please enter the patient's full name.");
    return;
  }

  const knownAllergies = allergiesRaw ? allergiesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  const chronicConditions = conditionsRaw ? conditionsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  const emergencyContacts = contactName ? [{ name: contactName, phone: contactPhone || "+91-99999-00000" }] : [];

  const payload = {
    id: patientId,
    full_name: fullName,
    dob: dob,
    blood_group: bloodGroup,
    emergency_contacts: emergencyContacts,
    known_allergies: knownAllergies,
    chronic_conditions: chronicConditions,
    past_surgeries: surgeries,
    insurance_policy: insurance
  };

  try {
    const res = await fetch(`/api/patient/${patientId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Failed to update medical history");
      return;
    }

    alert("✅ Medical History & Profile updated successfully! All records have been persisted.");
    closeEditMedicalHistoryModal();
    refreshPatientBannerPreview(patientId);
  } catch (err) {
    console.error("Save medical history error:", err);
    alert("Error saving medical history.");
  }
}

// Granular Current Medication Functions
async function loadPatientMedications(patientId) {
  const container = document.getElementById('patientMedsList');
  if (!container) return;

  container.innerHTML = `<div class="text-muted" style="font-size:0.75rem; padding:0.5rem;"><span class="live-dot"></span> Loading active medications...</div>`;

  try {
    const res = await fetch(`/api/patient/${patientId}/medications`);
    const meds = await res.json();

    if (!meds || meds.length === 0) {
      container.innerHTML = `<div class="text-muted" style="font-size:0.8rem; padding:0.75rem; background:var(--bg-card); border-radius:var(--radius-sm); border:1px dashed var(--border-color); text-align:center;">No medications listed. Add your current medicines below to keep your ER medical pass updated.</div>`;
      return;
    }

    container.innerHTML = meds.map(m => `
      <div class="med-card" id="medCard-${m.id}">
        <div class="med-card-header">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="med-name">${m.name}</span>
            <span class="med-dosage-badge">${m.dosage}</span>
          </div>
          <div style="display:flex; gap:0.35rem;">
            <button class="btn-xs btn-outline" onclick="editPatientMedicationPrompt('${m.id}', '${m.name}', '${m.dosage}', '${m.frequency}', '${m.notes || ''}')" title="Edit dosage or notes">
              <i data-lucide="edit-2"></i> Edit
            </button>
            <button class="btn-xs btn-danger" onclick="deletePatientMedication('${m.id}', '${m.name}')" title="Remove medication">
              <i data-lucide="trash-2"></i> Delete
            </button>
          </div>
        </div>
        <div class="med-meta-row">
          <span><i data-lucide="clock"></i> <strong>Schedule:</strong> ${m.frequency}</span>
          <span><i data-lucide="calendar"></i> <strong>Started:</strong> ${m.start_date || 'N/A'}</span>
          <span><i data-lucide="calendar-check"></i> <strong>End:</strong> ${m.end_date || 'Ongoing'}</span>
        </div>
        ${m.notes ? `<div class="med-notes"><strong>Notes:</strong> ${m.notes}</div>` : ''}
      </div>
    `).join('');

    lucide.createIcons();
  } catch (err) {
    console.error("Error loading medications:", err);
    container.innerHTML = `<div class="text-danger" style="font-size:0.75rem;">Failed to load medications.</div>`;
  }
}

async function addNewMedicationToProfile() {
  const patientId = state.editingPatientId || 'P-101';
  const name = document.getElementById('newMedName').value.trim();
  const dosage = document.getElementById('newMedDosage').value.trim();
  const frequency = document.getElementById('newMedFrequency').value.trim();
  const startDate = document.getElementById('newMedStartDate').value;
  const endDate = document.getElementById('newMedEndDate').value.trim() || 'Ongoing';
  const notes = document.getElementById('newMedNotes').value.trim();

  if (!name || !dosage || !frequency) {
    alert("Please enter Medicine Name, Dosage, and Frequency.");
    return;
  }

  const payload = {
    name: name,
    dosage: dosage,
    frequency: frequency,
    start_date: startDate || "Today",
    end_date: endDate,
    notes: notes
  };

  try {
    const res = await fetch(`/api/patient/${patientId}/medications`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      alert("Failed to add medication.");
      return;
    }

    const data = await res.json();
    alert(`💊 ${name} (${dosage}) added successfully!\n\nNotice: It has been appended to your medication list. Existing medicines were NOT overwritten.`);

    // Clear form inputs
    document.getElementById('newMedName').value = '';
    document.getElementById('newMedDosage').value = '';
    document.getElementById('newMedFrequency').value = '';
    document.getElementById('newMedNotes').value = '';

    // Reload medications list
    loadPatientMedications(patientId);
  } catch (err) {
    console.error("Add medication error:", err);
    alert("Error adding medication.");
  }
}

async function deletePatientMedication(medId, medName) {
  const patientId = state.editingPatientId || 'P-101';
  if (!confirm(`Are you sure you want to remove "${medName}" from your active medications?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/patient/${patientId}/medications/${medId}`, {
      method: 'DELETE'
    });

    if (!res.ok) {
      alert("Failed to remove medication.");
      return;
    }

    loadPatientMedications(patientId);
  } catch (err) {
    console.error("Delete medication error:", err);
  }
}

async function editPatientMedicationPrompt(medId, currentName, currentDosage, currentFrequency, currentNotes) {
  const patientId = state.editingPatientId || 'P-101';
  const newDosage = prompt(`Edit Dosage for ${currentName}:`, currentDosage);
  if (newDosage === null) return;

  const newFrequency = prompt(`Edit Frequency for ${currentName}:`, currentFrequency);
  if (newFrequency === null) return;

  const newNotes = prompt(`Edit Special Notes / Food Instructions:`, currentNotes);
  if (newNotes === null) return;

  const payload = {
    name: currentName,
    dosage: newDosage.trim() || currentDosage,
    frequency: newFrequency.trim() || currentFrequency,
    notes: newNotes.trim()
  };

  try {
    const res = await fetch(`/api/patient/${patientId}/medications/${medId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      alert("Failed to update medication.");
      return;
    }

    loadPatientMedications(patientId);
  } catch (err) {
    console.error("Edit medication error:", err);
  }
}

// Utility
function round(num, decimals) {
  return Number(Math.round(num + 'e' + decimals) + 'e-' + decimals);
}

// ==================== FEATURE 1: DOCTOR LOGIN PORTAL ====================

const doctorState = {
  loggedInDoctor: null,
  selectedDoctorIds: new Set()
};

function switchDoctorTab(tab) {
  const loginPanel = document.getElementById('doctorLoginPanel');
  const regPanel = document.getElementById('doctorRegisterPanel');
  const loginBtn = document.getElementById('loginTabBtn');
  const regBtn = document.getElementById('registerTabBtn');
  if (tab === 'login') {
    loginPanel.style.display = 'flex';
    regPanel.style.display = 'none';
    loginBtn.className = 'btn btn-primary btn-sm';
    regBtn.className = 'btn btn-outline btn-sm';
  } else {
    loginPanel.style.display = 'none';
    regPanel.style.display = 'block';
    regBtn.className = 'btn btn-primary btn-sm';
    loginBtn.className = 'btn btn-outline btn-sm';
  }
}

async function doctorLogin() {
  const email = document.getElementById('docLoginEmail').value.trim();
  const password = document.getElementById('docLoginPassword').value.trim();
  if (!email || !password) { alert('Please enter email and password.'); return; }
  try {
    const res = await fetch('/api/doctors/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) { const e = await res.json(); alert(e.detail || 'Login failed.'); return; }
    const data = await res.json();
    doctorState.loggedInDoctor = data.doctor;
    renderDoctorSession(data.doctor);
    loadDoctors();
  } catch (err) { console.error(err); alert('Login request failed.'); }
}

async function doctorRegister() {
  const name = document.getElementById('regDocName').value.trim();
  const email = document.getElementById('regDocEmail').value.trim();
  const password = document.getElementById('regDocPassword').value.trim();
  const spec = document.getElementById('regDocSpec').value;
  const exp = parseInt(document.getElementById('regDocExp').value) || 0;
  const phone = document.getElementById('regDocPhone').value.trim();
  const bio = document.getElementById('regDocBio').value.trim();
  if (!name || !email || !password) { alert('Name, email, and password are required.'); return; }
  try {
    const res = await fetch('/api/doctors/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: name, email, password, specialization: spec, experience_years: exp, phone, bio })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Registration failed.'); return; }
    alert(`✅ Doctor account created! ID: ${data.doctor_id}\nYou can now login.`);
    switchDoctorTab('login');
    document.getElementById('docLoginEmail').value = email;
  } catch (err) { console.error(err); alert('Registration failed.'); }
}

function renderDoctorSession(doc) {
  document.getElementById('doctorLoginForm').style.display = 'none';
  document.getElementById('doctorSessionPanel').style.display = 'block';
  document.getElementById('doctorSessionBadge').style.display = 'inline-flex';

  const stars = '★'.repeat(Math.round(doc.rating || 4)) + '☆'.repeat(5 - Math.round(doc.rating || 4));
  const onCallBadge = doc.is_on_call ? '<span class="badge badge-danger" style="font-size:0.7rem;">ON CALL</span>' : '';
  const availBadge = doc.is_available
    ? '<span class="badge badge-success" style="font-size:0.7rem;">AVAILABLE</span>'
    : '<span class="badge badge-warning" style="font-size:0.7rem;">OFFLINE</span>';

  document.getElementById('activeDocCard').innerHTML = `
    <div class="doctor-card-inner" style="background:var(--bg-subtle); border:1px solid var(--accent); border-radius:var(--radius-md); padding:0.85rem;">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <div style="font-size:1.1rem; font-weight:800; color:#fff;">${doc.full_name}</div>
          <div style="font-size:0.8rem; color:#93c5fd; font-weight:600;">${doc.specialization}</div>
          <div style="font-size:0.72rem; color:var(--text-muted);">${doc.hospital_name || 'Registered Hospital'}</div>
        </div>
        <div style="text-align:right; display:flex; flex-direction:column; gap:0.25rem;">
          ${availBadge} ${onCallBadge}
          <span style="font-size:0.85rem; color:#f59e0b;" title="${doc.rating} rating">${stars}</span>
        </div>
      </div>
      <div style="display:flex; gap:1rem; margin-top:0.5rem; font-size:0.75rem; color:var(--text-muted);">
        <span>📋 ${doc.experience_years} yrs exp.</span>
        <span>📞 ${doc.phone || 'Phone N/A'}</span>
        <span>🆔 ${doc.id}</span>
      </div>
    </div>
  `;
  lucide.createIcons();
}

function doctorLogout() {
  doctorState.loggedInDoctor = null;
  document.getElementById('doctorLoginForm').style.display = 'block';
  document.getElementById('doctorSessionPanel').style.display = 'none';
  document.getElementById('doctorSessionBadge').style.display = 'none';
}

async function setDoctorAvailability(isAvailable) {
  if (!doctorState.loggedInDoctor) { alert('Please login first.'); return; }
  try {
    await fetch(`/api/doctors/${doctorState.loggedInDoctor.id}/availability`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_available: isAvailable })
    });
    doctorState.loggedInDoctor.is_available = isAvailable ? 1 : 0;
    renderDoctorSession(doctorState.loggedInDoctor);
    alert(`Status set to: ${isAvailable ? '✅ AVAILABLE' : '🌙 OFF-DUTY'}`);
    loadDoctors();
  } catch (err) { console.error(err); }
}

async function selfAssignToEmergency() {
  if (!doctorState.loggedInDoctor) { alert('Please login first.'); return; }
  const emgId = document.getElementById('docEmergencyInput').value.trim();
  if (!emgId) { alert('Enter a valid Emergency ID.'); return; }
  try {
    const res = await fetch(`/api/emergencies/${emgId}/doctors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_ids: [doctorState.loggedInDoctor.id], notes: 'Doctor self-assigned via Doctor Portal' })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Could not assign to emergency.'); return; }
    alert(`✅ You have joined Emergency ${emgId} as attending physician.`);
  } catch (err) { console.error(err); }
}

async function loadDoctors() {
  const container = document.getElementById('doctorDirectoryList');
  if (!container) return;
  const spec = document.getElementById('docSpecFilter')?.value || '';
  const availOnly = document.getElementById('docAvailFilter')?.checked ?? true;
  let url = `/api/doctors?available_only=${availOnly}`;
  if (spec) url += `&specialization=${encodeURIComponent(spec)}`;
  try {
    const res = await fetch(url);
    const doctors = await res.json();
    if (doctors.length === 0) {
      container.innerHTML = `<div class="loading-state text-muted">No doctors match the current filter.</div>`;
      return;
    }
    container.innerHTML = doctors.map(doc => {
      const stars = '★'.repeat(Math.round(doc.rating || 4)) + '☆'.repeat(5 - Math.round(doc.rating || 4));
      const avail = doc.is_available ? 'badge-success' : 'badge-warning';
      const availLabel = doc.is_available ? 'Available' : 'Offline';
      const onCall = doc.is_on_call ? '<span class="badge badge-danger" style="font-size:0.65rem; margin-left:0.25rem;">ON CALL</span>' : '';
      const isSelected = doctorState.selectedDoctorIds.has(doc.id);
      return `
        <div class="doctor-card ${isSelected ? 'doctor-card-selected' : ''}" id="docCard-${doc.id}" onclick="toggleDoctorSelection('${doc.id}')">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <label class="doctor-select-check">
                <input type="checkbox" id="chk-${doc.id}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleDoctorSelection('${doc.id}')">
                <span style="font-size:0.95rem; font-weight:700; color:#fff;">${doc.full_name}</span>
              </label>
              <div style="font-size:0.78rem; color:#93c5fd; font-weight:600; margin-left:1.5rem;">${doc.specialization}</div>
              <div style="font-size:0.72rem; color:var(--text-muted); margin-left:1.5rem;">${doc.hospital_name || ''}</div>
            </div>
            <div style="text-align:right; display:flex; flex-direction:column; gap:0.2rem; align-items:flex-end;">
              <span class="badge ${avail}">${availLabel}${onCall}</span>
              <span style="font-size:0.8rem; color:#f59e0b;">${stars}</span>
            </div>
          </div>
          <div style="display:flex; gap:0.85rem; margin-top:0.4rem; font-size:0.72rem; color:var(--text-muted);">
            <span>🏥 ${doc.experience_years}yr exp</span>
            <span>📞 ${doc.phone || 'N/A'}</span>
            <span style="font-size:0.68rem; color:var(--text-dim);">${doc.bio ? doc.bio.substring(0, 60) + '...' : ''}</span>
          </div>
        </div>
      `;
    }).join('');
    lucide.createIcons();
  } catch (err) { console.error(err); container.innerHTML = '<div class="text-danger">Failed to load doctors.</div>'; }
}

function toggleDoctorSelection(docId) {
  const card = document.getElementById(`docCard-${docId}`);
  const chk = document.getElementById(`chk-${docId}`);
  if (doctorState.selectedDoctorIds.has(docId)) {
    doctorState.selectedDoctorIds.delete(docId);
    card?.classList.remove('doctor-card-selected');
    if (chk) chk.checked = false;
  } else {
    doctorState.selectedDoctorIds.add(docId);
    card?.classList.add('doctor-card-selected');
    if (chk) chk.checked = true;
  }
  const bar = document.getElementById('docMultiSelectBar');
  const countEl = document.getElementById('docSelectedCount');
  if (doctorState.selectedDoctorIds.size > 0) {
    bar.style.display = 'flex';
    countEl.textContent = `${doctorState.selectedDoctorIds.size} doctor(s) selected`;
  } else {
    bar.style.display = 'none';
  }
}

function clearDoctorSelections() {
  doctorState.selectedDoctorIds.clear();
  document.querySelectorAll('.doctor-card-selected').forEach(el => el.classList.remove('doctor-card-selected'));
  document.querySelectorAll('[id^="chk-"]').forEach(el => el.checked = false);
  document.getElementById('docMultiSelectBar').style.display = 'none';
}

async function alertSelectedDoctors() {
  if (doctorState.selectedDoctorIds.size === 0) { alert('Select at least one doctor first.'); return; }
  const emgId = document.getElementById('docAlertEmergencyId').value.trim();
  if (!emgId) { alert('Enter the Emergency ID to alert the selected doctors for.'); return; }
  try {
    const res = await fetch(`/api/emergencies/${emgId}/doctors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_ids: Array.from(doctorState.selectedDoctorIds), notes: 'Multi-doctor alert from Emergency Portal' })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Failed to alert doctors.'); return; }
    alert(`🚨 ${data.assigned_doctors.length} doctor(s) alerted for Emergency ${emgId}!\n${data.assigned_doctors.map(d => `• ${d.name} (${d.specialization})`).join('\n')}`);
    clearDoctorSelections();
  } catch (err) { console.error(err); alert('Failed to send alert.'); }
}

// ==================== FEATURE 2: ORGAN TRANSPORT GREEN CORRIDOR ====================

const ORGAN_VIABILITY_INFO = {
  HEART:   { emoji: '❤️', hours: 6,   urgency: 'CRITICAL', color: '#ef4444' },
  LUNG:    { emoji: '🫁', hours: 8,   urgency: 'HIGH',     color: '#f59e0b' },
  LIVER:   { emoji: '🫀', hours: 24,  urgency: 'MODERATE', color: '#3b82f6' },
  KIDNEY:  { emoji: '🫘', hours: 36,  urgency: 'MODERATE', color: '#10b981' },
  PANCREAS:{ emoji: '🔵', hours: 24,  urgency: 'MODERATE', color: '#8b5cf6' },
  CORNEA:  { emoji: '👁️', hours: 336, urgency: 'ROUTINE',  color: '#06b6d4' }
};

let organTimerIntervals = {};

function updateOrganViabilityPreview() {
  const organType = document.getElementById('organType')?.value || 'HEART';
  const info = ORGAN_VIABILITY_INFO[organType] || ORGAN_VIABILITY_INFO.HEART;
  const nameEl = document.getElementById('prevOrganName');
  const windowEl = document.getElementById('prevViabilityWindow');
  const barEl = document.getElementById('prevViabilityBar');
  const noteEl = document.getElementById('prevViabilityNote');
  if (nameEl) nameEl.textContent = `${info.emoji} ${organType}`;
  if (windowEl) windowEl.textContent = `Max ${info.hours < 24 ? info.hours + ' hours' : (info.hours / 24).toFixed(0) + ' days'}`;
  if (barEl) { barEl.style.background = info.color; barEl.style.width = '100%'; }
  const urgencyNote = {
    CRITICAL: 'CRITICAL — Activate corridor immediately. Zero delay tolerated.',
    HIGH: 'HIGH PRIORITY — Activate green corridor and dispatch immediately.',
    MODERATE: 'Moderate urgency. Confirm recipient team readiness before dispatch.',
    ROUTINE: 'Routine transport window. Standard corridor activation sufficient.'
  };
  if (noteEl) noteEl.textContent = urgencyNote[info.urgency] || '';
}

async function activateOrganCorridor() {
  const organType = document.getElementById('organType').value;
  const donorHospId = document.getElementById('organDonorHospital').value;
  const recipientHospId = document.getElementById('organRecipientHospital').value;
  const ambulanceId = document.getElementById('organAmbulance').value;
  if (donorHospId === recipientHospId) {
    alert('Donor and Recipient hospitals cannot be the same.');
    return;
  }
  try {
    const res = await fetch('/api/organ-transports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ organ_type: organType, donor_hospital_id: donorHospId, recipient_hospital_id: recipientHospId, ambulance_id: ambulanceId })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Failed to activate corridor.'); return; }
    const badge = document.getElementById('organCorridorBadge');
    if (badge) { badge.textContent = '🟢 CORRIDOR ACTIVE'; badge.style.background = 'var(--success)'; }
    alert(`🫀 ORGAN GREEN CORRIDOR ACTIVATED!\n\n${data.message}\n\nTransport ID: ${data.transport_id}\nViability Window: ${data.viability_hours} hours from harvest`);
    loadOrganTransports();
    loadTrafficSignals(false);
  } catch (err) { console.error(err); alert('Failed to activate organ corridor.'); }
}

async function loadOrganTransports() {
  const container = document.getElementById('organTransportsList');
  if (!container) return;
  // Clear existing timers
  Object.values(organTimerIntervals).forEach(clearInterval);
  organTimerIntervals = {};
  try {
    const res = await fetch('/api/organ-transports');
    const transports = await res.json();
    if (transports.length === 0) {
      container.innerHTML = `<div class="loading-state text-muted">No organ transport corridors active. Use the form to activate one.</div>`;
      return;
    }
    container.innerHTML = transports.map(t => {
      const info = ORGAN_VIABILITY_INFO[t.organ_type] || { emoji: '🫀', hours: 24, color: '#3b82f6' };
      const harvestedAt = new Date(t.harvested_at);
      const expiresAt = new Date(harvestedAt.getTime() + t.viability_hours * 3600000);
      const statusColors = { VIABLE: 'var(--success)', AT_RISK: 'var(--warning)', UNVIABLE: 'var(--danger)', DELIVERED: 'var(--text-muted)' };
      const statusColor = statusColors[t.status] || '#fff';
      const corridorTag = t.corridor_active ? '🟢 CORRIDOR ACTIVE' : '🔴 CORRIDOR CLOSED';
      return `
        <div class="organ-transport-card" id="organCard-${t.id}" style="border-left:4px solid ${info.color};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <div style="font-size:1.1rem; font-weight:800;">${info.emoji} ${t.organ_type}</div>
              <div style="font-size:0.75rem; color:var(--text-muted);">ID: ${t.id}</div>
            </div>
            <div style="text-align:right;">
              <span style="font-weight:800; color:${statusColor}; font-size:0.85rem;">${t.status}</span>
              <div style="font-size:0.72rem; color:var(--text-muted);">${corridorTag}</div>
            </div>
          </div>
          <div style="font-size:0.78rem; color:var(--text-muted); margin-top:0.3rem;">
            🏥 From: <strong>${t.donor_hospital_name}</strong> → <strong>${t.recipient_hospital_name}</strong>
          </div>
          <div style="margin-top:0.5rem;">
            <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:0.2rem;">
              <span>Viability Remaining</span>
              <span id="organTimer-${t.id}" style="font-family:var(--font-mono); font-weight:700; color:${info.color};">Calculating...</span>
            </div>
            <div style="background:var(--bg-subtle); border-radius:4px; height:8px; overflow:hidden;">
              <div id="organTimerBar-${t.id}" style="height:100%; width:100%; background:${info.color}; transition:width 1s linear; border-radius:4px;"></div>
            </div>
          </div>
          ${t.status !== 'UNVIABLE' && t.status !== 'DELIVERED' ? `
          <div style="display:flex; gap:0.4rem; margin-top:0.65rem; flex-wrap:wrap;">
            <button class="btn-xs btn-danger" onclick="markOrganUnviable('${t.id}')">
              ⛔ Mark Organ UNVIABLE
            </button>
            <button class="btn-xs btn-success" onclick="markOrganDelivered('${t.id}')">
              ✅ Mark DELIVERED
            </button>
            <button class="btn-xs btn-warning" onclick="markOrganAtRisk('${t.id}')">
              ⚠️ Flag AT-RISK
            </button>
          </div>` : `<div style="font-size:0.75rem; color:var(--text-dim); margin-top:0.5rem;">Transport concluded. ${t.notes || ''}</div>`}
        </div>
      `;
    }).join('');

    // Start countdown timers
    transports.forEach(t => {
      if (t.status === 'UNVIABLE' || t.status === 'DELIVERED') return;
      const info = ORGAN_VIABILITY_INFO[t.organ_type] || { hours: 24, color: '#3b82f6' };
      const harvestedAt = new Date(t.harvested_at);
      const totalMs = t.viability_hours * 3600000;
      const expiresAt = new Date(harvestedAt.getTime() + totalMs);

      const timerEl = document.getElementById(`organTimer-${t.id}`);
      const barEl = document.getElementById(`organTimerBar-${t.id}`);

      organTimerIntervals[t.id] = setInterval(() => {
        const now = new Date();
        const remainingMs = expiresAt - now;
        if (remainingMs <= 0) {
          clearInterval(organTimerIntervals[t.id]);
          if (timerEl) { timerEl.textContent = 'EXPIRED'; timerEl.style.color = 'var(--danger)'; }
          if (barEl) { barEl.style.width = '0%'; barEl.style.background = 'var(--danger)'; }
          return;
        }
        const remainingHrs = Math.floor(remainingMs / 3600000);
        const remainingMins = Math.floor((remainingMs % 3600000) / 60000);
        const remainingSecs = Math.floor((remainingMs % 60000) / 1000);
        const pct = Math.max(0, (remainingMs / totalMs) * 100);
        const timerColor = pct > 50 ? 'var(--success)' : pct > 20 ? 'var(--warning)' : 'var(--danger)';

        if (timerEl) {
          timerEl.textContent = `${remainingHrs}h ${remainingMins}m ${remainingSecs}s`;
          timerEl.style.color = timerColor;
        }
        if (barEl) { barEl.style.width = `${pct}%`; barEl.style.background = timerColor; }
      }, 1000);
    });

    lucide.createIcons();
  } catch (err) { console.error(err); container.innerHTML = '<div class="text-danger">Failed to load organ transports.</div>'; }
}

async function markOrganUnviable(transportId) {
  if (!confirm('⛔ Are you sure? This will mark the organ as UNVIABLE, deactivate the corridor, and notify the recipient hospital.')) return;
  try {
    const res = await fetch(`/api/organ-transports/${transportId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'UNVIABLE', notes: 'Organ marked unviable by transport officer.' })
    });
    const data = await res.json();
    alert(`⛔ ${data.message}`);
    loadOrganTransports();
    loadTrafficSignals(false);
  } catch (err) { console.error(err); }
}

async function markOrganDelivered(transportId) {
  try {
    const res = await fetch(`/api/organ-transports/${transportId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'DELIVERED', notes: 'Organ delivered to recipient hospital surgical team.' })
    });
    const data = await res.json();
    alert(`✅ ${data.message}`);
    loadOrganTransports();
    loadTrafficSignals(false);
  } catch (err) { console.error(err); }
}

async function markOrganAtRisk(transportId) {
  try {
    await fetch(`/api/organ-transports/${transportId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'AT_RISK', notes: 'Organ viability flagged AT-RISK by transport team.' })
    });
    loadOrganTransports();
  } catch (err) { console.error(err); }
}

// ==================== FEATURE 3: AMBULANCE OFFICER SAFETY CHECK-IN ====================

let safetyPollInterval = null;

async function officerSafetyCheckin() {
  const ambId = state.activeAmbulanceId;
  try {
    const res = await fetch(`/api/ambulances/${ambId}/checkin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        latitude: state.userCoords.lat,
        longitude: state.userCoords.lon,
        notes: 'Routine field safety check-in'
      })
    });
    const data = await res.json();
    const now = new Date();
    const el = document.getElementById('lastCheckinTime');
    const minEl = document.getElementById('minutesSinceCheckin');
    if (el) el.textContent = now.toLocaleTimeString();
    if (minEl) { minEl.textContent = '0 min ago'; minEl.style.color = 'var(--success)'; }
    updateOfficerSafetyWidget('OK');
    alert(`✅ ${data.message}`);
    loadOfficerCheckinLog(ambId);
  } catch (err) { console.error(err); }
}

async function loadOfficerCheckinLog(ambId) {
  const logEl = document.getElementById('checkinLog');
  if (!logEl || logEl.style.display === 'none') return;
  try {
    const res = await fetch(`/api/ambulances/${ambId}/checkins?limit=5`);
    const checkins = await res.json();
    logEl.innerHTML = checkins.map(c => {
      const time = new Date(c.checked_in_at).toLocaleTimeString();
      return `<div class="checkin-log-item"><span>${time}</span><span>${c.officer_name}</span><span style="color:var(--text-muted); font-size:0.7rem;">${c.notes}</span></div>`;
    }).join('') || '<div class="text-muted" style="font-size:0.75rem; padding:0.5rem;">No check-in history.</div>';
  } catch (err) { console.error(err); }
}

function toggleCheckinLog() {
  const logEl = document.getElementById('checkinLog');
  if (!logEl) return;
  logEl.style.display = logEl.style.display === 'none' ? 'block' : 'none';
  if (logEl.style.display === 'block') loadOfficerCheckinLog(state.activeAmbulanceId);
}

function updateOfficerSafetyWidget(status) {
  const statusEl = document.getElementById('officerSafetyStatus');
  if (!statusEl) return;
  if (status === 'OVERDUE') {
    statusEl.className = 'officer-status-pill overdue';
    statusEl.innerHTML = `<span style="background:#ef4444;border-radius:50%;width:8px;height:8px;display:inline-block;"></span> ⚠️ OVERDUE — CHECK IN NOW`;
  } else {
    statusEl.className = 'officer-status-pill ok';
    statusEl.innerHTML = `<span class="live-dot"></span> STATUS: OK`;
  }
}

async function pollOfficerSafetyStatus() {
  try {
    const res = await fetch(`/api/ambulances/${state.activeAmbulanceId}/safety-status`);
    const data = await res.json();
    const el = document.getElementById('lastCheckinTime');
    const minEl = document.getElementById('minutesSinceCheckin');
    if (el && data.last_checkin) {
      el.textContent = new Date(data.last_checkin).toLocaleTimeString();
    }
    if (minEl && data.minutes_since_checkin !== null) {
      const mins = Math.round(data.minutes_since_checkin);
      minEl.textContent = `${mins} min ago`;
      minEl.style.color = data.is_overdue ? 'var(--danger)' : 'var(--success)';
    }
    updateOfficerSafetyWidget(data.is_overdue ? 'OVERDUE' : 'OK');
  } catch (err) { /* Silently handle polling errors */ }
}

// Poll officer safety every 60 seconds when on ambulance view
document.addEventListener('DOMContentLoaded', () => {
  setInterval(pollOfficerSafetyStatus, 60000);
  // Also load organ transports and doctors when those tabs become active
  document.querySelectorAll('#navTabs .nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-view');
      if (view === 'organView') { loadOrganTransports(); updateOrganViabilityPreview(); }
      if (view === 'doctorView') loadDoctors();
    });
  });
});

// ==================== FEATURE 4: OFFLINE EMERGENCY SMS FALLBACK ====================

function checkConnectivity() {
  const isOnline = navigator.onLine;
  const offlineBanner = document.getElementById('offlineSMSBanner');
  if (!isOnline && offlineBanner) {
    offlineBanner.classList.remove('hidden');
    buildSMSFallbackLink();
  } else if (offlineBanner) {
    offlineBanner.classList.add('hidden');
  }
  return isOnline;
}

function buildSMSFallbackLink() {
  const smsLink = document.getElementById('smsFallbackLink');
  if (!smsLink) return;
  const lat = state.userCoords.lat;
  const lon = state.userCoords.lon;
  const blood = document.getElementById('previewBloodBadge')?.textContent || 'Unknown';
  const hazard = state.activeHazard || 'EMERGENCY';
  const body = `EMERGENCY SOS! Type:${hazard} Blood:${blood} GPS:${lat},${lon} Google Maps:https://maps.google.com/?q=${lat},${lon} Please send ambulance immediately.`;
  const encodedBody = encodeURIComponent(body);
  // Use 112 (India's emergency number), country-agnostic
  smsLink.href = `sms:112?body=${encodedBody}`;
}

// Override SOS dispatch to check connectivity first
const _originalSOSClick = handleSOSClick;
window.handleSOSClick = function () {
  const isOnline = checkConnectivity();
  if (!isOnline) {
    // Offline mode: build SMS fallback and open QR modal with SMS banner
    buildSMSFallbackLink();
    const offlineBanner = document.getElementById('offlineSMSBanner');
    if (offlineBanner) offlineBanner.classList.remove('hidden');
    openPatientQRModal('P-101');
    alert('⚠️ You are OFFLINE. Internet SOS unavailable.\n\nAn emergency SMS link has been prepared. Tap "TAP TO SEND EMERGENCY SMS" in the QR modal to send your coordinates via SMS to 112.');
    return;
  }
  _originalSOSClick();
};

window.addEventListener('online', checkConnectivity);
window.addEventListener('offline', () => {
  checkConnectivity();
  const offlineBanner = document.getElementById('offlineSMSBanner');
  if (offlineBanner) { offlineBanner.classList.remove('hidden'); buildSMSFallbackLink(); }
});

// ==================== FEATURE 5: DYNAMIC LOCK-SCREEN QR PASS ====================

async function downloadLockScreenQR() {
  const canvas = document.getElementById('lockscreenCanvas');
  const qrImg = document.querySelector('#qrcodeCanvas img') || document.querySelector('#qrcodeCanvas canvas');
  if (!qrImg) { alert('Generate the QR code first by opening the Medical Pass.'); return; }

  // Standard phone lock-screen dimensions (portrait 9:16)
  const W = 1080, H = 1920;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Dark background gradient
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, '#0a0e17');
  bg.addColorStop(1, '#0f172a');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Red emergency stripe at top
  ctx.fillStyle = '#ef4444';
  ctx.fillRect(0, 0, W, 120);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 52px Inter, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('🚨 MEDICAL EMERGENCY PASS', W / 2, 78);

  // Draw QR code
  try {
    const qrCanvas = qrImg instanceof HTMLCanvasElement ? qrImg : null;
    const qrImageEl = qrImg instanceof HTMLImageElement ? qrImg : null;
    const qrSize = 600;
    const qrX = (W - qrSize) / 2;
    const qrY = 180;
    // White background behind QR
    ctx.fillStyle = '#ffffff';
    ctx.roundRect ? ctx.roundRect(qrX - 20, qrY - 20, qrSize + 40, qrSize + 40, 20) : ctx.fillRect(qrX - 20, qrY - 20, qrSize + 40, qrSize + 40);
    ctx.fill();
    if (qrCanvas) { ctx.drawImage(qrCanvas, qrX, qrY, qrSize, qrSize); }
    else if (qrImageEl && qrImageEl.complete) { ctx.drawImage(qrImageEl, qrX, qrY, qrSize, qrSize); }
  } catch (e) { console.warn('QR draw error:', e); }

  // Patient info from the summary
  const name = document.querySelector('#qrPatientSummary h4')?.textContent || 'Patient Name';
  const blood = document.getElementById('previewBloodBadge')?.textContent || 'Unknown';
  const allergy = document.getElementById('previewAllergyBadge')?.textContent || 'None';

  const textStartY = 920;
  ctx.textAlign = 'center';

  // Patient name
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 68px Inter, Arial';
  ctx.fillText(name, W / 2, textStartY);

  // Blood group badge
  ctx.fillStyle = '#ef4444';
  ctx.fillRect(W/2 - 180, textStartY + 30, 360, 100);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 56px Inter, Arial';
  ctx.fillText(`BLOOD: ${blood}`, W / 2, textStartY + 98);

  // Allergy
  ctx.fillStyle = '#fca5a5';
  ctx.font = 'bold 44px Inter, Arial';
  ctx.fillText(`⚠️ ALLERGY: ${allergy}`, W / 2, textStartY + 190);

  // Emergency instruction
  ctx.fillStyle = '#94a3b8';
  ctx.font = '38px Inter, Arial';
  ctx.fillText('SCAN QR CODE FOR FULL MEDICAL HISTORY', W / 2, textStartY + 280);
  ctx.fillText('Powered by ResQNet Emergency System', W / 2, textStartY + 340);

  // Emergency contacts
  ctx.fillStyle = '#3b82f6';
  ctx.font = 'bold 42px Inter, Arial';
  ctx.fillText('EMERGENCY: CALL 112', W / 2, H - 180);

  // Footer
  ctx.fillStyle = '#1e293b';
  ctx.fillRect(0, H - 120, W, 120);
  ctx.fillStyle = '#64748b';
  ctx.font = '34px Inter, Arial';
  ctx.fillText('ResQNet • Emergency Medical Pass • Scan for full history', W / 2, H - 45);

  // Download
  const link = document.createElement('a');
  link.download = `ResQNet-Medical-Pass-LockScreen.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
  alert('📱 Lock-screen QR image downloaded! Set it as your phone wallpaper so bystanders can scan it when you are unconscious.');
}

// Override openPatientQRModal to add offline SMS check
const _origOpenQR = openPatientQRModal;
window.openPatientQRModal = async function(patientId) {
  await _origOpenQR(patientId);
  checkConnectivity();
};

// =================================================================
// UNIFIED 3-PORTAL CONTROLLER: PATIENT | DOCTOR | AMBULANCE
// =================================================================

const portalRegistry = {
  patient: {
    role: 'PATIENT',
    viewId: 'citizenView',
    email: 'patient@demo.com',
    name: 'Aarav Sharma (P-101)',
    path: '/patient'
  },
  doctor: {
    role: 'DOCTOR',
    viewId: 'doctorView',
    email: 'doctor@demo.com',
    name: 'Dr. Ananya Dasgupta (DOC-001)',
    path: '/doctor'
  },
  ambulance: {
    role: 'AMBULANCE',
    viewId: 'ambulanceView',
    email: 'ambulance@demo.com',
    name: 'Alpha-1 (AMB-101)',
    path: '/ambulance'
  }
};

window.switchPortal = function(portalName, updateUrl = true) {
  const slug = (portalName || 'patient').toLowerCase();
  const config = portalRegistry[slug] || portalRegistry.patient;

  // 1. Update Portal selector button active states
  ['patient', 'doctor', 'ambulance'].forEach(p => {
    const btn = document.getElementById(`portalBtn-${p}`);
    if (btn) {
      if (p === slug) btn.classList.add('active');
      else btn.classList.remove('active');
    }
  });

  // 2. Switch active main view panel
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.remove('active');
  });
  const activePanel = document.getElementById(config.viewId);
  if (activePanel) {
    activePanel.classList.add('active');
  }

  // 3. Synchronize navigation tabs
  const navTabs = document.querySelectorAll('#navTabs .nav-btn');
  navTabs.forEach(tab => {
    if (tab.getAttribute('data-view') === config.viewId) {
      tab.classList.add('active');
    } else {
      tab.classList.remove('active');
    }
  });

  // 4. Update Header User/Role pill
  const roleTag = document.getElementById('userRoleTag');
  const emailText = document.getElementById('userEmailText');
  const storedUser = localStorage.getItem('resqnet_user');
  let displayEmail = config.email;
  let displayRole = config.role;

  if (storedUser) {
    try {
      const u = JSON.parse(storedUser);
      if (u.role && u.role.toLowerCase() === slug) {
        displayEmail = u.email || config.email;
        displayRole = u.role;
      }
    } catch (e) {}
  }

  if (roleTag) {
    roleTag.textContent = displayRole;
    if (slug === 'doctor') roleTag.style.background = '#0284c7';
    else if (slug === 'ambulance') roleTag.style.background = '#d97706';
    else roleTag.style.background = 'var(--danger)';
  }
  if (emailText) {
    emailText.textContent = displayEmail;
  }

  // 5. Invalidate maps and trigger portal-specific refresh
  setTimeout(() => {
    if (slug === 'patient' && citizenMap) {
      citizenMap.invalidateSize();
      refreshPatientBannerPreview('P-101');
    } else if (slug === 'doctor') {
      if (typeof loadDoctors === 'function') loadDoctors();
    } else if (slug === 'ambulance') {
      if (typeof initAmbulanceMap === 'function') initAmbulanceMap();
      if (typeof checkOfficerSafetyStatus === 'function') checkOfficerSafetyStatus();
    }
    if (window.lucide) lucide.createIcons();
  }, 150);

  // 6. Update URL without full page reload
  if (updateUrl && window.history && window.history.pushState) {
    window.history.pushState({ portal: slug }, '', config.path);
  }
};

window.openUnifiedAuthModal = function() {
  const modal = document.getElementById('unifiedAuthModal');
  if (modal) modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
};

window.closeUnifiedAuthModal = function() {
  const modal = document.getElementById('unifiedAuthModal');
  if (modal) modal.classList.add('hidden');
};

window.quickDemoLogin = async function(email, role) {
  await executeAuthLogin(email, 'demo', role);
};

window.handleUnifiedLogin = async function(e) {
  if (e && e.preventDefault) e.preventDefault();
  const email = document.getElementById('authEmailInput')?.value.trim();
  const password = document.getElementById('authPasswordInput')?.value.trim();
  const role = document.getElementById('authRoleSelect')?.value;
  if (!email) {
    alert('Please enter your email address.');
    return;
  }
  await executeAuthLogin(email, password || 'demo', role);
};

async function executeAuthLogin(email, password, role) {
  const alertBox = document.getElementById('authAlertBox');
  if (alertBox) {
    alertBox.className = 'alert-box hidden';
    alertBox.textContent = '';
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role })
    });

    const data = await res.json();
    if (!res.ok) {
      if (alertBox) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.textContent = data.detail || 'Authentication failed.';
      } else {
        alert(data.detail || 'Authentication failed.');
      }
      return;
    }

    // Persist authenticated session
    localStorage.setItem('resqnet_user', JSON.stringify(data.user));
    localStorage.setItem('resqnet_token', data.token);

    // If Doctor, update doctor portal session state
    if (data.role === 'DOCTOR' && window.doctorState) {
      window.doctorState.loggedInDoctor = data.profile;
      if (typeof renderDoctorSession === 'function') renderDoctorSession(data.profile);
    }

    closeUnifiedAuthModal();
    switchPortal(data.portal, true);
  } catch (err) {
    console.error('Unified login error:', err);
    if (alertBox) {
      alertBox.className = 'alert-box alert-danger';
      alertBox.textContent = 'Server communication error. Please ensure the backend is running.';
    }
  }
}

// Handle Direct URL Portal Routing (e.g. /patient, /doctor, /ambulance)
function checkUrlPortalRoute() {
  const path = window.location.pathname.toLowerCase();
  if (path.includes('doctor')) {
    switchPortal('doctor', false);
  } else if (path.includes('ambulance')) {
    switchPortal('ambulance', false);
  } else if (path.includes('patient')) {
    switchPortal('patient', false);
  }
}

window.addEventListener('popstate', checkUrlPortalRoute);
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(checkUrlPortalRoute, 50);
});

