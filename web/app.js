/**
 * Main Application Controller for AETHERIS-ADR
 * Handles event wiring, API communication, WebSocket telemetry streaming, and UI updates.
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Initialize Visualizer and Dashboard
  const visualizer = new DebrisVisualizer3D('three-canvas-container');
  const dashboard = new DashboardManager();

  let catalogObjects = [];
  let selectedObject = null;
  let currentFilter = 'ALL';

  // -------------------------------------------------------------------------
  // 1. Clock & System Telemetry Header
  // -------------------------------------------------------------------------
  function updateClock() {
    const now = new Date();
    const clockEl = document.getElementById('utc-clock');
    if (clockEl) {
      clockEl.textContent = 'UTC ' + now.toISOString().substring(11, 19);
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  // -------------------------------------------------------------------------
  // 2. Fetch Catalog & Populate Debris List
  // -------------------------------------------------------------------------
  async function fetchCatalog() {
    try {
      const res = await fetch('/api/catalog?limit=500');
      const data = await res.json();
      catalogObjects = data.objects || [];

      document.getElementById('val-catalog-count').textContent = `${catalogObjects.length} OBJECTS`;
      const criticalCount = catalogObjects.filter(o => o.criticality_score >= 50.0).length;
      document.getElementById('val-critical-count').textContent = `${criticalCount} DETECTED`;

      renderDebrisList();
      visualizer.updateDebrisCatalog(catalogObjects);

      // Select first high-criticality object by default (e.g. ENVISAT)
      if (catalogObjects.length > 0) {
        selectDebrisObject(catalogObjects[0]);
      }
    } catch (err) {
      console.error('Failed to load catalog:', err);
    }
  }

  function renderDebrisList() {
    const container = document.getElementById('debris-list-container');
    const searchVal = (document.getElementById('debris-search').value || '').toLowerCase();
    container.innerHTML = '';

    const filtered = catalogObjects.filter(obj => {
      if (currentFilter !== 'ALL' && obj.object_type !== currentFilter) return false;
      if (searchVal) {
        return obj.name.toLowerCase().includes(searchVal) || String(obj.norad_id).includes(searchVal);
      }
      return true;
    });

    filtered.forEach(obj => {
      const card = document.createElement('div');
      card.className = 'debris-card' + (selectedObject && selectedObject.norad_id === obj.norad_id ? ' selected' : '');
      
      let scoreClass = 'moderate';
      if (obj.criticality_score >= 60.0) scoreClass = 'critical';
      else if (obj.criticality_score >= 30.0) scoreClass = 'high';

      card.innerHTML = `
        <div class="debris-card-top">
          <span class="debris-card-name">${obj.name}</span>
          <span class="debris-card-score ${scoreClass}">C: ${obj.criticality_score}</span>
        </div>
        <div class="debris-card-meta">
          <span>NORAD ${obj.norad_id}</span>
          <span>Alt: ${obj.perigee_alt_km} km</span>
          <span>Mass: ${obj.estimated_mass_kg} kg</span>
        </div>
      `;

      card.addEventListener('click', () => selectDebrisObject(obj));
      container.appendChild(card);
    });
  }

  // Filter chips
  document.querySelectorAll('.filter-chips .chip').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-chips .chip').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentFilter = e.target.getAttribute('data-filter');
      renderDebrisList();
    });
  });

  document.getElementById('debris-search').addEventListener('input', () => {
    renderDebrisList();
  });

  // -------------------------------------------------------------------------
  // 3. Debris Selection & Detail Inspection
  // -------------------------------------------------------------------------
  async function selectDebrisObject(obj) {
    selectedObject = obj;
    renderDebrisList();
    visualizer.selectObject(obj.norad_id);

    // Update Top HUD
    document.getElementById('hud-target-name').textContent = `${obj.name} (NORAD ${obj.norad_id})`;
    document.getElementById('hud-target-alt').textContent = `${obj.perigee_alt_km} km`;
    document.getElementById('hud-target-mass').textContent = `${obj.estimated_mass_kg.toLocaleString()} kg`;
    document.getElementById('hud-target-criticality').textContent = `${obj.criticality_score} / 100`;

    // Fetch instant prediction state vector
    try {
      const predRes = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ norad_id: obj.norad_id })
      });
      const predData = await predRes.json();
      const st = predData.state;

      // Update Telemetry tab
      document.getElementById('tel-pos-x').textContent = st.position_eci_km[0].toFixed(1);
      document.getElementById('tel-pos-y').textContent = st.position_eci_km[1].toFixed(1);
      document.getElementById('tel-pos-z').textContent = st.position_eci_km[2].toFixed(1);

      document.getElementById('tel-vel-x').textContent = st.velocity_eci_kms[0].toFixed(2);
      document.getElementById('tel-vel-y').textContent = st.velocity_eci_kms[1].toFixed(2);
      document.getElementById('tel-vel-z').textContent = st.velocity_eci_kms[2].toFixed(2);

      document.getElementById('hud-target-speed').textContent = `${st.speed_kms.toFixed(2)} km/s`;

      document.getElementById('tel-sma').textContent = `${st.keplerian.semi_major_axis_km} km`;
      document.getElementById('tel-ecc').textContent = st.keplerian.eccentricity.toFixed(5);
      document.getElementById('tel-inc').textContent = `${st.keplerian.inclination_deg}°`;
      document.getElementById('tel-raan').textContent = `${st.keplerian.raan_deg}°`;
      document.getElementById('tel-period').textContent = `${st.keplerian.period_min} min`;
      document.getElementById('tel-raan-drift').textContent = `${obj.j2_raan_drift_deg_per_day >= 0 ? '+' : ''}${obj.j2_raan_drift_deg_per_day.toFixed(3)} °/day`;

      document.getElementById('tel-ballistic').textContent = `${obj.ballistic_coefficient_kg_m2.toFixed(1)} kg/m²`;
      document.getElementById('tel-area').textContent = `${obj.cross_sectional_area_m2} m²`;
      document.getElementById('tel-rcs').textContent = `${obj.radar_cross_section_m2} m²`;
      document.getElementById('tel-pcoll').textContent = obj.collision_probability_annual ? obj.collision_probability_annual.toExponential(2) : '1.2e-4';

      dashboard.renderMaterialBreakdown(obj.material_breakdown);

      // Auto-evaluate aerothermal demise & Point Nemo deorbit for selected object
      evaluateDisposal(obj.norad_id);
    } catch (err) {
      console.error('Prediction query error:', err);
    }
  }

  // -------------------------------------------------------------------------
  // 4. Disposal Physics & Point Nemo Evaluation
  // -------------------------------------------------------------------------
  async function evaluateDisposal(noradId) {
    try {
      // 1. Aerothermal Demise Call
      const demRes = await fetch('/api/reentry/aerothermal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ norad_id: noradId })
      });
      const demData = await demRes.json();

      document.getElementById('demise-peak-flux').textContent = `${demData.peak_heat_flux_mw_m2} MW/m²`;
      document.getElementById('demise-breakup-alt').textContent = `${demData.breakup_altitude_km} km`;
      document.getElementById('demise-survived-mass').textContent = `${demData.total_surviving_mass_kg} kg (${(100 - demData.mass_demised_percent).toFixed(1)}%)`;
      document.getElementById('demise-casualty-area').textContent = `${demData.estimated_casualty_area_m2} m²`;

      const card = document.getElementById('card-decision');
      if (demData.is_safe_demise) {
        card.style.background = 'rgba(0, 230, 118, 0.12)';
        card.style.borderColor = 'var(--accent-emerald)';
        card.querySelector('.decision-title').style.color = 'var(--accent-emerald)';
        card.querySelector('.decision-title').textContent = 'SAFE HIGH-ALTITUDE ATMOSPHERIC INCINERATION';
        card.querySelector('.decision-reason').textContent = 'Structure is predominantly Aluminum with no heavy refractory tanks; complete thermal demise occurs above 70 km altitude.';
      } else {
        card.style.background = 'rgba(255, 23, 68, 0.12)';
        card.style.borderColor = 'var(--accent-crimson)';
        card.querySelector('.decision-title').style.color = 'var(--accent-crimson)';
        card.querySelector('.decision-title').textContent = 'MANDATORY POINT NEMO TARGETED REENTRY';
        card.querySelector('.decision-reason').textContent = 'Object contains dense Titanium/Stainless components exceeding the 8 m² ground casualty area threshold.';
      }

      dashboard.updateDemiseData(demData);

      // 2. Ion Beam Shepherd (IBS) Contactless Deorbit Evaluation
      await evaluateIBS(noradId);

      // 3. Point Nemo Deorbit Targeter Call
      const nemoRes = await fetch('/api/reentry/point_nemo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ norad_id: noradId })
      });
      const nemoData = await nemoRes.json();

      document.getElementById('nemo-dv').textContent = `${nemoData.delta_v_ms} m/s`;
      document.getElementById('nemo-prop').textContent = `${nemoData.propellant_required_kg} kg`;
      document.getElementById('nemo-gamma').textContent = `${nemoData.entry_flight_path_angle_deg}°`;
      document.getElementById('nemo-ellipse').textContent = `${nemoData.dispersion_ellipse.along_track_sigma_km} × ${nemoData.dispersion_ellipse.cross_track_sigma_km} km`;
    } catch (err) {
      console.error('Disposal evaluation error:', err);
    }
  }

  async function evaluateIBS(noradId) {
    if (!noradId && selectedObject) noradId = selectedObject.norad_id;
    if (!noradId) return;

    const standoff = parseFloat(document.getElementById('slider-ibs-standoff').value) || 20.0;
    const thrust = parseFloat(document.getElementById('slider-ibs-thrust').value) || 200.0;

    document.getElementById('val-ibs-standoff').textContent = `${standoff.toFixed(1)} m`;
    document.getElementById('val-ibs-thrust').textContent = `${thrust.toFixed(0)} mN`;

    try {
      const res = await fetch('/api/reentry/ion_beam_shepherd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          norad_id: noradId,
          standoff_distance_m: standoff,
          beam_thrust_mn: thrust
        })
      });
      const data = await res.json();

      document.getElementById('ibs-eta').textContent = `${data.flux_interception_efficiency_percent}%`;
      document.getElementById('ibs-net-push').textContent = `${data.net_target_push_force_mn} mN`;
      document.getElementById('ibs-recoil').textContent = `${data.station_keeping_compensation_force_mn} mN`;
      document.getElementById('ibs-dwell-days').textContent = `${data.deorbit_dwell_duration_days} Days`;
      document.getElementById('ibs-daily-prop').textContent = `${data.daily_propellant_consumption_kg_day} kg/day`;
      document.getElementById('ibs-total-prop').textContent = `${data.total_chaser_propellant_used_kg} kg`;
    } catch (err) {
      console.error('IBS evaluation error:', err);
    }
  }

  document.getElementById('slider-ibs-standoff').addEventListener('input', () => {
    document.getElementById('val-ibs-standoff').textContent = `${parseFloat(document.getElementById('slider-ibs-standoff').value).toFixed(1)} m`;
  });
  document.getElementById('slider-ibs-standoff').addEventListener('change', () => evaluateIBS());

  document.getElementById('slider-ibs-thrust').addEventListener('input', () => {
    document.getElementById('val-ibs-thrust').textContent = `${parseFloat(document.getElementById('slider-ibs-thrust').value).toFixed(0)} mN`;
  });
  document.getElementById('slider-ibs-thrust').addEventListener('change', () => evaluateIBS());

  document.getElementById('btn-compute-ibs-dwell').addEventListener('click', () => evaluateIBS());

  // -------------------------------------------------------------------------
  // 5. Fleet Optimizer Trigger
  // -------------------------------------------------------------------------
  async function runFleetOptimizer() {
    const btn = document.getElementById('btn-run-fleet-optimizer');
    btn.textContent = 'Solving Orbital VRP with J2 Drift...';
    btn.disabled = true;

    const targetsCount = parseInt(document.getElementById('inp-fleet-targets').value) || 15;
    const propMass = parseFloat(document.getElementById('inp-fleet-prop').value) || 800.0;

    try {
      const res = await fetch('/api/fleet/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          top_n_critical_targets: targetsCount,
          chaser_propellant_capacity_kg: propMass
        })
      });
      const data = await res.json();

      document.getElementById('fleet-kmin').textContent = `${data.summary.minimum_robots_needed} ROBOTS`;
      document.getElementById('fleet-savings').textContent = `${data.summary.average_propellant_savings_percent}%`;
      document.getElementById('fleet-duration').textContent = `${data.summary.mean_mission_duration_days} DAYS`;

      dashboard.renderFleetItineraries(data.robots);
    } catch (err) {
      console.error('Fleet optimization error:', err);
    } finally {
      btn.textContent = 'Optimize Minimum Robot Fleet Size (K_min)';
      btn.disabled = false;
    }
  }

  document.getElementById('btn-run-fleet-optimizer').addEventListener('click', runFleetOptimizer);

  // -------------------------------------------------------------------------
  // 6. Kessler Cascade Simulation Slider
  // -------------------------------------------------------------------------
  async function updateKesslerSimulation() {
    const rate = parseInt(document.getElementById('slider-adr-rate').value);
    document.getElementById('lbl-adr-rate').textContent = `${rate} targets / year`;

    try {
      const res = await fetch('/api/kessler/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adr_removal_rate_per_year: rate })
      });
      const data = await res.json();

      dashboard.updateKesslerData(data);
      document.getElementById('kessler-reduction').textContent = `-${data.scenario.risk_reduction_pct}% Risk`;
      if (rate >= 8) {
        document.getElementById('kessler-verdict').textContent = 'STABILIZED SUSTAINABLE';
        document.getElementById('kessler-verdict').className = 'val green';
      } else {
        document.getElementById('kessler-verdict').textContent = 'UNSTABLE CASCADE RISK';
        document.getElementById('kessler-verdict').className = 'val alert';
      }
    } catch (err) {
      console.error('Kessler simulation error:', err);
    }
  }

  document.getElementById('slider-adr-rate').addEventListener('input', updateKesslerSimulation);

  // -------------------------------------------------------------------------
  // 7. Tab Switching Logic
  // -------------------------------------------------------------------------
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      e.target.classList.add('active');
      const tabKey = e.target.getAttribute('data-tab');
      document.getElementById(`tab-${tabKey}`).classList.add('active');
    });
  });

  // -------------------------------------------------------------------------
  // 8. 3D Viewport Controls
  // -------------------------------------------------------------------------
  document.getElementById('btn-toggle-orbits').addEventListener('click', (e) => {
    const active = visualizer.toggleOrbits();
    e.target.classList.toggle('active', active);
  });

  document.getElementById('btn-toggle-point-nemo').addEventListener('click', (e) => {
    const active = visualizer.togglePointNemo();
    e.target.classList.toggle('active', active);
  });

  document.getElementById('btn-reset-cam').addEventListener('click', () => {
    visualizer.resetCamera();
  });

  document.getElementById('btn-track-target').addEventListener('click', (e) => {
    visualizer.trackingSelected = !visualizer.trackingSelected;
    e.target.classList.toggle('active', visualizer.trackingSelected);
  });

  document.getElementById('btn-propagate-hpop').addEventListener('click', async () => {
    if (!selectedObject) return;
    const btn = document.getElementById('btn-propagate-hpop');
    btn.textContent = 'Integrating Cowell RK45...';
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          norad_id: selectedObject.norad_id,
          use_high_precision_hpop: true,
          duration_seconds: 5400.0,
          step_seconds: 60.0
        })
      });
      const data = await res.json();
      alert(`HPOP Numerical Propagation complete: ${data.points_count} high-precision trajectory points computed across 1 full orbit incorporating J2-J4 geopotential, dynamic atmospheric drag, SRP, and lunisolar gravity.`);
    } catch (err) {
      console.error('HPOP run error:', err);
    } finally {
      btn.textContent = 'Run HPOP Numerical';
    }
  });

  // Initial Load
  await fetchCatalog();
  runFleetOptimizer();
  updateKesslerSimulation();
});
