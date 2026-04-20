// ─── Utilities ───────────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function postJson(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(r => r.json());
}

function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function fmtDatetime(ts) {
  return new Date(ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ─── Command sender (shared by Dashboard + Manage) ────────────────────────────
function sendCmd(cmd) {
  postJson('/api/command', { command: cmd })
    .then(data => {
      const el = $('cmd-response');
      if (!el) return;
      if (data.error) {
        el.textContent = `Error: ${data.error}`;
        return;
      }
      if (cmd === 'STATUS') {
        el.textContent = 'Fetching status…';
        setTimeout(() => {
          fetch('/api/latest').then(r => r.json()).then(d => {
            if (!d || !d.timestamp) { el.textContent = 'No data yet.'; return; }
            el.textContent =
              `STATUS — Temp: ${d.temperature}°C | Hum: ${d.humidity}% | Fan: ${d.fan_state ? 'ON' : 'OFF'} | Servo: ${d.servo_state ? 'Open' : 'Closed'}`;
            setTimeout(() => { el.textContent = ''; }, 6000);
          });
        }, 2000);
      } else {
        el.textContent = `✓ Sent: ${cmd}`;
        setTimeout(() => { el.textContent = ''; }, 3000);
      }
    });
}

// ─── DASHBOARD PAGE ───────────────────────────────────────────────────────────
let sensorChart = null;
let currentMetric = 'temperature';
let currentHours = 1;

const metricConfig = {
  temperature: { label: 'Temperature', color: '#CC2200', yMin: 0,  yMax: 50,   stepSize: 5,   yTitle: '°C',    binary: false },
  humidity:    { label: 'Humidity',    color: '#0066CC', yMin: 0,  yMax: 100,  stepSize: 10,  yTitle: '%',     binary: false },
  bowl_weight: { label: 'Bowl Weight', color: '#4A90D9', yMin: 0,  yMax: 1000, stepSize: 100, yTitle: 'Grams', binary: false },
  ir_state:    { label: 'Presence',    color: '#1a6e2e', yMin: 0,  yMax: 1,    stepSize: 1,   yTitle: 'Presence', binary: true  },
  fan_state:   { label: 'Fan',         color: '#E07B00', yMin: 0,  yMax: 1,    stepSize: 1,   yTitle: 'Fan',   binary: true  }
};

function fetchLatest() {
  fetch('/api/latest')
    .then(r => r.json())
    .then(data => {
      if (!data || !data.timestamp) return;
      setText('temperature', data.temperature ?? '--');
      setText('humidity',    data.humidity    ?? '--');
      setText('bowl-weight', data.bowl_weight != null ? parseFloat(data.bowl_weight).toFixed(1) : '--');
      setText('cat-weight',  data.cat_weight_kg != null ? data.cat_weight_kg : '--');
      setText('ir-state',    data.ir_state  ? 'YES'    : 'NO');
      setText('visits-today', data.rfid_today ?? '--');
      setText('fan-state',   data.fan_state ? 'ON'     : 'OFF');
      setText('servo-state', data.servo_state ? 'OPEN' : 'CLOSED');
      setText('last-updated', data.timestamp);
    });
}

function downsample5min(rows) {
  const buckets = {};
  rows.forEach(r => {
    const d = new Date(r.timestamp);
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}-${Math.floor(d.getMinutes() / 5)}`;
    if (!buckets[key]) buckets[key] = r;
    else buckets[key] = r; // keep last value in each bucket
  });
  return Object.values(buckets);
}

function fetchHistory(hours) {
  fetch(`/api/history?hours=${hours}`)
    .then(r => r.json())
    .then(rows => {
      renderChart(downsample5min(rows), currentMetric);
    });
}

function fetchLatestReadings() {
  fetch('/api/latest-readings?limit=10')
    .then(r => r.json())
    .then(rows => renderHistoryTable(rows));
}

function renderChart(rows, metric) {
  const cfg = metricConfig[metric];

  const binaryTickCb = metric === 'ir_state'
    ? v => v === 1 ? 'Detected' : v === 0 ? 'Clear' : ''
    : v => v === 1 ? 'ON' : v === 0 ? 'OFF' : '';

  const yAxisOpts = cfg.binary
    ? {
        min: 0, max: 1,
        title: { display: true, text: cfg.yTitle, font: { family: 'Inter', size: 11 }, color: '#888' },
        ticks: { font: { family: 'Inter', size: 11 }, stepSize: 1, callback: binaryTickCb },
        grid: { color: '#eee' }
      }
    : {
        min: cfg.yMin, max: cfg.yMax,
        title: { display: true, text: cfg.yTitle, font: { family: 'Inter', size: 11 }, color: '#888' },
        ticks: { font: { family: 'Inter', size: 11 }, stepSize: cfg.stepSize },
        grid: { color: '#eee' }
      };

  const stepSizeMap = { 1: 5, 6: 30, 12: 60, 24: 120 };
  const xStepSize = stepSizeMap[currentHours] || Math.ceil(currentHours * 60 / 12 / 5) * 5;

  let xMin, xMax;
  if (rows.length > 0) {
    const times = rows.map(r => new Date(r.timestamp).getTime());
    const firstMs = Math.min(...times);
    const lastMs  = Math.max(...times);
    xMax = new Date(lastMs);
    xMin = new Date(Math.max(firstMs, lastMs - currentHours * 3600000));
  } else {
    xMax = new Date();
    xMin = new Date(xMax.getTime() - currentHours * 3600000);
  }

  const xMinMs = xMin.getTime();
  const xMaxMs = xMax.getTime();

  const pad2 = n => String(n).padStart(2, '0');
  const fmtHHmm = d => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;

  const xAxisOpts = {
    type: 'time',
    min: xMin.toISOString(),
    max: xMax.toISOString(),
    time: { tooltipFormat: 'HH:mm:ss' },
    afterBuildTicks(scale) {
      scale.ticks = [
        { value: xMinMs },
        { value: xMaxMs }
      ];
    },
    ticks: {
      font: { family: 'Inter', size: 11 },
      maxRotation: 0,
      autoSkip: false,
      callback(value) {
        const d = new Date(value);
        return fmtHHmm(d);
      }
    },
    grid: { color: '#eee', drawTicks: false }
  };

  // Always destroy and recreate on metric change to cleanly apply all axis options
  if (sensorChart) {
    sensorChart.destroy();
    sensorChart = null;
  }

  const ctx = $('sensorChart');
  if (!ctx) return;

  const pointData = rows.map(r => ({ x: r.timestamp, y: r[metric] }));

  sensorChart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [{
        label: cfg.label,
        data: pointData,
        borderColor: cfg.color,
        backgroundColor: cfg.color + '18',
        borderWidth: 1.5,
        pointRadius: rows.length > 30 ? 0 : 3,
        tension: cfg.binary ? 0 : 0.3,
        stepped: cfg.binary ? 'before' : false,
        fill: true
      }]
    },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { display: false } },
      scales: { x: xAxisOpts, y: yAxisOpts }
    }
  });
  sensorChart._isBinary = cfg.binary;
}

function renderHistoryTable(rows) {
  const tbody = $('history-tbody');
  if (!tbody) return;
  tbody.innerHTML = rows.length
    ? rows.map(r => `
        <tr>
          <td>${fmtDatetime(r.timestamp)}</td>
          <td>${r.temperature ?? '--'}</td>
          <td>${r.humidity ?? '--'}</td>
          <td>${r.bowl_weight != null ? parseFloat(r.bowl_weight).toFixed(1) + ' g' : '--'}</td>
          <td>${r.ir_state ? '● Detected' : 'Clear'}</td>
          <td>${r.fan_state ? 'ON' : 'OFF'}</td>
          <td>${r.servo_state ? 'Open' : 'Closed'}</td>
        </tr>`).join('')
    : '<tr><td colspan="7">No data yet.</td></tr>';
}

function initDashboard() {
  fetchLatest();
  setInterval(fetchLatest, 3000);

  fetchHistory(currentHours);
  setInterval(() => fetchHistory(currentHours), 30000);

  fetchLatestReadings();
  setInterval(fetchLatestReadings, 10000);

  document.querySelectorAll('#metric-tabs .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#metric-tabs .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMetric = btn.dataset.metric;
      fetchHistory(currentHours);
    });
  });

  document.querySelectorAll('#time-tabs .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#time-tabs .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentHours = parseInt(btn.dataset.hours);
      fetchHistory(currentHours);
    });
  });
}

// ─── ANALYTICS PAGE ───────────────────────────────────────────────────────────
function fetchAnalytics(hours) {
  fetch(`/api/analytics?hours=${hours}`)
    .then(r => r.json())
    .then(d => {
      setText('stat-temp-avg',    d.temp_avg    != null ? d.temp_avg    : '--');
      setText('stat-temp-range',  d.temp_min    != null ? `${d.temp_min} – ${d.temp_max}` : '--');
      setText('stat-hum-avg',     d.hum_avg     != null ? d.hum_avg     : '--');
      setText('stat-hum-range',   d.hum_min     != null ? `${d.hum_min} – ${d.hum_max}` : '--');
      setText('stat-fan-pct',     d.fan_on_pct  != null ? d.fan_on_pct  : '--');
      setText('stat-feed-count',  d.feed_count  != null ? d.feed_count  : '--');
      setText('stat-feed-avg',    d.feed_avg_per_day != null ? d.feed_avg_per_day : '--');
      setText('stat-rfid-total',  d.rfid_total  != null ? d.rfid_total  : '--');
      setText('stat-rfid-avg',    d.rfid_avg_per_day != null ? d.rfid_avg_per_day : '--');
      setText('stat-portion-avg', d.avg_portion != null ? d.avg_portion : '--');
    });
}

function fetchFeedLog() {
  fetch('/api/feedlog?limit=20')
    .then(r => r.json())
    .then(rows => {
      const tbody = $('feedlog-tbody');
      if (!tbody) return;
      tbody.innerHTML = rows.length
        ? rows.map(r => `
            <tr>
              <td>${r.id}</td>
              <td>${r.pet ?? 'Unknown'}</td>
              <td>${r.trigger ?? '--'}</td>
              <td>${r.portion_grams != null ? parseFloat(r.portion_grams).toFixed(1) + ' g' : '--'}</td>
              <td>${fmtDatetime(r.timestamp)}</td>
            </tr>`).join('')
        : '<tr><td colspan="5">No feed events recorded.</td></tr>';
    });
}

function initAnalytics() {
  let activeHours = 24;
  fetchAnalytics(activeHours);
  fetchFeedLog();

  document.querySelectorAll('#analytics-time-tabs .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#analytics-time-tabs .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeHours = parseInt(btn.dataset.hours);
      fetchAnalytics(activeHours);
    });
  });
}

// ─── MANAGE PAGE ──────────────────────────────────────────────────────────────
function loadSchedules() {
  fetch('/api/schedules')
    .then(r => r.json())
    .then(schedules => {
      const container = $('schedule-list');
      if (!container) return;
      if (!schedules.length) {
        container.innerHTML = '<p class="response-text">No schedules set.</p>';
        return;
      }
      container.innerHTML = schedules.map(s => {
        const lastTrig = s.last_triggered
          ? `<span style="font-size:0.75rem;color:#aaa;">Last: ${fmtDatetime(s.last_triggered)}</span>`
          : `<span style="font-size:0.75rem;color:#ccc;">Never triggered</span>`;
        return `
          <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
            <span style="font-weight:600;font-size:0.95rem;">${s.time_of_day}</span>
            ${lastTrig}
            <button class="btn btn-danger" style="padding:0.25rem 0.75rem;font-size:0.75rem;"
              onclick="deleteSchedule(${s.id})">Remove</button>
          </div>`;
      }).join('');
    });
}

function addSchedule() {
  const input = $('new-schedule-time');
  const status = $('schedule-status');
  if (!input || !input.value) {
    if (status) status.textContent = 'Please pick a time.';
    return;
  }
  postJson('/api/schedules', { time_of_day: input.value })
    .then(data => {
      if (data.error) {
        if (status) status.textContent = `Error: ${data.error}`;
        return;
      }
      input.value = '';
      loadSchedules();
      if (status) {
        status.textContent = '✓ Schedule added.';
        setTimeout(() => { status.textContent = ''; }, 3000);
      }
    });
}

function deleteSchedule(id) {
  fetch(`/api/schedules/${id}`, { method: 'DELETE' })
    .then(() => loadSchedules());
}

// ─── PET PROFILES ─────────────────────────────────────────────────────────────
function loadPets() {
  fetch('/api/pets')
    .then(r => r.json())
    .then(pets => {
      const tbody = $('pets-tbody');
      if (!tbody) return;
      if (!pets.length) {
        tbody.innerHTML = '<tr><td colspan="6">No pets added yet.</td></tr>';
        return;
      }
      tbody.innerHTML = pets.map(p => `
        <tr>
          <td>${p.name}</td>
          <td>${p.rfid_uid || '—'}</td>
          <td>${p.weight_kg != null ? p.weight_kg.toFixed(2) + ' kg' : '—'}</td>
          <td>
            <input type="number" step="0.1" min="1" max="200"
              value="${p.food_per_kg != null ? p.food_per_kg : 60}"
              style="width:70px;padding:0.25rem 0.4rem;border:1px solid #ccc;font-size:0.85rem;"
              onchange="saveFoodPerKg(${p.id}, this.value)" />
            <span style="font-size:0.78rem;color:#aaa;">g/kg</span>
          </td>
          <td>${p.calc_portion != null ? p.calc_portion.toFixed(1) + ' g' : '—'}</td>
          <td>
            <button class="btn btn-danger" style="padding:0.2rem 0.6rem;font-size:0.75rem;"
              onclick="deletePet(${p.id})">Remove</button>
          </td>
        </tr>`).join('');
    });
}

function saveFoodPerKg(petId, value) {
  postJson(`/api/pets/${petId}`, { food_per_kg: parseFloat(value) })
    .then(() => loadPets());
}

function addPet() {
  const nameEl = $('new-pet-name');
  const rfidEl = $('new-pet-rfid');
  const status = $('pets-status');
  if (!nameEl || !nameEl.value.trim()) {
    if (status) status.textContent = 'Please enter a name.';
    return;
  }
  postJson('/api/pets', { name: nameEl.value.trim(), rfid_uid: rfidEl ? rfidEl.value.trim() : '' })
    .then(data => {
      if (data.error) {
        if (status) status.textContent = `Error: ${data.error}`;
        return;
      }
      nameEl.value = '';
      if (rfidEl) rfidEl.value = '';
      loadPets();
      if (status) {
        status.textContent = '✓ Pet added.';
        setTimeout(() => { status.textContent = ''; }, 3000);
      }
    });
}

function deletePet(id) {
  if (!confirm('Remove this pet profile?')) return;
  fetch(`/api/pets/${id}`, { method: 'DELETE' })
    .then(() => loadPets());
}

function initManage() {
  const form = $('settings-form');
  if (form) {
    form.addEventListener('submit', e => {
      e.preventDefault();
      const payload = {};
      new FormData(form).forEach((val, key) => { payload[key] = val; });
      postJson('/api/settings', payload)
        .then(() => {
          const el = $('save-status');
          if (el) {
            el.textContent = '✓ Settings saved.';
            setTimeout(() => { el.textContent = ''; }, 3000);
          }
        });
    });
  }
  loadSchedules();
  loadPets();
}

// ─── Page router ─────────────────────────────────────────────────────────────
if ($('sensorChart'))  initDashboard();
if ($('stats-grid'))   initAnalytics();
if ($('settings-form') && !$('sensorChart')) initManage();

