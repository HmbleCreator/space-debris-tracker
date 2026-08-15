/**
 * Dashboard & Charting Components for AETHERIS-ADR
 * Handles Aerothermal Demise plots, Kessler Cascade charts, and Fleet Itinerary cards.
 */

class DashboardManager {
  constructor() {
    this.demiseChart = null;
    this.kesslerChart = null;
    this.initCharts();
  }

  initCharts() {
    // 1. Aerothermal Demise Chart
    const demiseCtx = document.getElementById('demise-chart');
    if (demiseCtx && typeof Chart !== 'undefined') {
      this.demiseChart = new Chart(demiseCtx, {
        type: 'line',
        data: {
          labels: [120, 100, 85, 75, 65, 55, 40, 25, 10, 0],
          datasets: [
            {
              label: 'Heat Flux (kW/m²)',
              data: [10, 45, 280, 850, 2450, 1800, 600, 120, 30, 0],
              borderColor: '#ff1744',
              backgroundColor: 'rgba(255, 23, 68, 0.1)',
              yAxisID: 'y1',
              tension: 0.3,
              fill: true
            },
            {
              label: 'Structure Temp (K)',
              data: [300, 380, 650, 855, 855, 855, 650, 420, 340, 300],
              borderColor: '#00e5ff',
              borderDash: [4, 4],
              yAxisID: 'y2',
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 9 } } }
          },
          scales: {
            x: {
              title: { display: true, text: 'Altitude (km)', color: '#64748b', font: { size: 9 } },
              ticks: { color: '#94a3b8', font: { size: 8 } },
              grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y1: {
              type: 'linear',
              position: 'left',
              title: { display: true, text: 'kW/m²', color: '#ff1744', font: { size: 9 } },
              ticks: { color: '#ff1744', font: { size: 8 } },
              grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y2: {
              type: 'linear',
              position: 'right',
              title: { display: true, text: 'Kelvin', color: '#00e5ff', font: { size: 9 } },
              ticks: { color: '#00e5ff', font: { size: 8 } },
              grid: { drawOnChartArea: false }
            }
          }
        }
      });
    }

    // 2. Kessler Cascade Chart
    const kesslerCtx = document.getElementById('kessler-chart');
    if (kesslerCtx && typeof Chart !== 'undefined') {
      const years = Array.from({ length: 31 }, (_, i) => 2026 + i);
      const baseline = years.map((_, i) => Math.round(37000 + i * 950 + i * i * 35));
      const adr10 = years.map((_, i) => Math.round(37000 + i * 380 - i * 150));

      this.kesslerChart = new Chart(kesslerCtx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [
            {
              label: 'Baseline (No ADR - Cascade Growth)',
              data: baseline,
              borderColor: '#ff1744',
              borderWidth: 2,
              pointRadius: 0,
              tension: 0.2
            },
            {
              label: 'With ADR (10 targets/year)',
              data: adr10,
              borderColor: '#00e676',
              borderWidth: 2.5,
              pointRadius: 0,
              fill: {
                target: 0,
                above: 'rgba(0, 230, 118, 0.08)'
              },
              tension: 0.2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 10 } } }
          },
          scales: {
            x: {
              ticks: { color: '#94a3b8', font: { size: 9 } },
              grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: {
              title: { display: true, text: 'Trackable Objects (>10cm)', color: '#94a3b8', font: { size: 9 } },
              ticks: { color: '#94a3b8', font: { size: 9 } },
              grid: { color: 'rgba(255,255,255,0.05)' }
            }
          }
        }
      });
    }
  }

  updateDemiseData(result) {
    if (!this.demiseChart || !result.profile) return;
    const profile = result.profile;
    if (profile.altitude_km && profile.altitude_km.length > 0) {
      this.demiseChart.data.labels = profile.altitude_km;
      this.demiseChart.data.datasets[0].data = profile.heat_flux_kw_m2;
      this.demiseChart.data.datasets[1].data = profile.temperature_k;
      this.demiseChart.update();
    }
  }

  updateKesslerData(kesslerData) {
    if (!this.kesslerChart || !kesslerData.scenario) return;
    this.kesslerChart.data.labels = kesslerData.scenario.years;
    this.kesslerChart.data.datasets[0].data = kesslerData.baseline.total_population;
    this.kesslerChart.data.datasets[1].data = kesslerData.scenario.total_population;
    this.kesslerChart.update();
  }

  renderMaterialBreakdown(materials) {
    const container = document.getElementById('material-bar');
    if (!container) return;
    container.innerHTML = '';

    const colors = {
      'ALUMINUM_6061': '#00e5ff',
      'TITANIUM_TI6AL4V': '#ffab00',
      'STAINLESS_STEEL_304': '#ff1744',
      'CARBON_COMPOSITE_CFRP': '#b388ff',
      'INCONEL_718': '#ff6d00'
    };

    for (const [mat, frac] of Object.entries(materials)) {
      const pct = (frac * 100).toFixed(0);
      if (pct <= 0) continue;
      const seg = document.createElement('div');
      seg.className = 'mat-segment';
      seg.style.width = `${pct}%`;
      seg.style.backgroundColor = colors[mat] || '#64748b';
      seg.title = `${mat}: ${pct}%`;
      container.appendChild(seg);
    }
  }

  renderFleetItineraries(robots) {
    const container = document.getElementById('robot-itinerary-list');
    if (!container) return;
    container.innerHTML = '';

    if (!robots || robots.length === 0) {
      container.innerHTML = '<div class="section-desc">No robot allocation computed. Click Optimize to generate.</div>';
      return;
    }

    robots.forEach(r => {
      const card = document.createElement('div');
      card.className = 'robot-card';
      
      let legsHtml = '';
      r.legs.forEach(leg => {
        const isDwell = leg.action_type === 'ION_BEAM_DEORBIT_DWELL';
        const badgeColor = isDwell ? '#b388ff' : '#00e5ff';
        legsHtml += `
          <div class="leg-item" style="border-left: 3px solid ${badgeColor}; padding-left: 8px; margin-bottom: 6px;">
            <span>[Leg ${leg.leg_index}] <strong style="color: ${badgeColor};">${leg.action_type}</strong>: <strong>${leg.target_name || 'Transit'}</strong></span>
            <div style="font-size: 10px; color: var(--text-muted); margin-top: 2px;">
              ${leg.description} &bull; <span style="color: var(--accent-cyan);">Duration: ${leg.duration_days}d &bull; Propellant: ${leg.propellant_used_kg}kg</span>
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="robot-card-header">
          <span>🛰️ ${r.robot_name} (${r.robot_id})</span>
          <span style="color: var(--accent-emerald);">${r.targets_removed_count} Targets Shepherded</span>
        </div>
        <div class="telemetry-grid" style="margin-bottom: 8px;">
          <div class="telemetry-item">
            <span class="lbl">Total Mission Duration</span>
            <span class="val highlight">${r.total_mission_duration_days} Days</span>
          </div>
          <div class="telemetry-item">
            <span class="lbl">Beam Dwell Time</span>
            <span class="val" style="color: #b388ff;">${r.total_dwell_days || 0} Days</span>
          </div>
          <div class="telemetry-item">
            <span class="lbl">Xenon Margin</span>
            <span class="val">${r.fuel_margin_percent}% (${r.final_remaining_propellant_kg}kg left)</span>
          </div>
        </div>
        <div class="legs-container">
          ${legsHtml}
        </div>
      `;
      container.appendChild(card);
    });
  }
}
