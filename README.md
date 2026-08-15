# AETHERIS-ADR
**Autonomous Ephemeris Tracking, Hazardous-debris Evaluation, Reentry & Interception System for Active Debris Removal**

A modular, high-fidelity astrodynamics simulation, risk mitigation, and autonomous robotics mission planning platform for space debris tracking, aerothermal demise analysis, Point Nemo targeted deorbit, and orbital Vehicle Routing Problem (VRP) fleet sizing.

---

## 🌟 Key Capabilities & 3-Layer Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                    AETHERIS-ADR SYSTEM ARCHITECTURE                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [LAYER 1: ORBITAL RISK & EPHEMERIS ENGINE]                                                         |
|  - Ingestion: Mean orbital elements & B* from TLE / synthetic populations                          |
|  - Fast Vectorized SGP4/J2 Secular Propagator (<1ms latency)                                       |
|  - High-Precision Numerical Propagator (HPOP / Cowell RK45 with J2-J6, NRLMSISE-00 drag, SRP)      |
|  - Environmental Criticality Index (Ci) & NASA SBM Fragment Yield Estimation                       |
|  - Multi-Decade Kessler Cascade Population Dynamics Simulator                                      |
|                                                                                                    |
|  [LAYER 2: AUTONOMOUS FLEET MISSION PLANNER (CENTERPIECE)]                                         |
|  - Non-Coplanar Rendezvous Delta-V Budget (Altitude + Plane Change + Phasing)                       |
|  - J2 Earth Oblateness Nodal Precession Drift Optimization (dOmega/dt)                             |
|  - Solves for Minimum Robots (K_min), Target Sequencing, and Tsiolkovsky Propellant Depletion      |
|  - Yields 70-90% Propellant Savings over direct impulsive plane changes                            |
|                                                                                                    |
|  [LAYER 3: AUTONOMOUS DISPOSAL & REENTRY PHYSICS]                                                  |
|  - Chaser Propulsion Engine: Impulsive Retro-Burn vs. Continuous Low-Thrust Ion Spiral             |
|  - Aerothermal Demise Simulator: Detra-Kemp-Riddell / Fay-Riddell Stagnation Heat Flux             |
|  - Multi-Material Thermal Demise & Ablation Tracking (Al 6061/7075, Ti-6Al-4V, SS 304, CFRP)     |
|  - Autonomous Decision: Safe Atmospheric Demise vs. Controlled Point Nemo (SPOUA) Targeting        |
|  - 3-Sigma Ground Impact Dispersion Ellipse Contained within SPOUA Maritime Corridor               |
|                                                                                                    |
|  [MISSION OPERATIONS CONSOLE & API]                                                                |
|  - FastAPI REST API & WebSocket Real-Time Telemetry Stream                                         |
|  - Interactive 3D WebGL / Three.js Mission Control with Orbit Trails, Heatmaps, and Fleet Gantt    |
+----------------------------------------------------------------------------------------------------+
```

---

## 📐 Mathematical Foundations

### 1. $J_2$ Earth Oblateness Nodal Precession Drift Rate
Natural RAAN secular precession rate:
$$\dot{\Omega} = -\frac{3}{2} J_2 \left(\frac{R_E}{p}\right)^2 n \cos i$$

The **Fleet Planner** exploits differences in $\dot{\Omega}$ between a designated drift orbit altitude $h_{\text{drift}}$ and the target orbit:
$$\Delta t_{\text{drift}} = \frac{\Delta \Omega}{\dot{\Omega}(h_{\text{drift}}, i) - \dot{\Omega}(h_{\text{target}}, i)}$$
This strategy avoids direct impulsive plane change $\Delta v = 2 v \sin(\Delta \theta / 2)$, saving up to 90% of propellant.

### 2. Environmental Criticality Index ($C_i$)
Quantifies the environmental hazard of object $i$:
$$C_i = M_i \cdot \sqrt{A_i} \cdot \rho_{\text{spatial}}(h_i, i_i) \cdot P_{\text{coll}}(i) \cdot \sqrt{N_{\text{frags}}(M_i)} \cdot \tau_{\text{decay}}(h_i)$$

### 3. Aerothermal Demise Stagnation Heat Flux
Stagnation point aerothermal convective heating:
$$q_{\text{stag}} = C_{\text{DKR}} \sqrt{\frac{\rho}{R_{\text{eff}}}} V_\infty^3$$
Coupled with component thermal capacitance and latent heat of fusion:
$$m c_p \frac{dT}{dt} = \dot{Q}_{\text{aero}} - \dot{Q}_{\text{rad}}, \qquad \dot{m}_{\text{abl}} = \frac{\dot{Q}_{\text{aero}} - \dot{Q}_{\text{rad}}}{H_f}$$

### 4. Tsiolkovsky Mass Depletion
Propellant consumed during maneuver $\Delta v$:
$$m_{\text{prop}} = m_{\text{total}} \left( 1 - \exp\left(-\frac{\Delta v}{I_{sp} g_0}\right) \right)$$

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+
- `fastapi`, `uvicorn`, `numpy`, `scipy`, `pytest`, `requests`

### Launch the Mission Operations Platform
```powershell
python run_server.py
```
Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)** to access the Interactive 3D Mission Control Console.

### Run the Test Suite
```powershell
python -m pytest tests/ -v
```

---

## 🛰️ REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System health, catalog count, and status |
| `GET` | `/api/catalog` | Filter and search space debris catalog |
| `GET` | `/api/catalog/{norad_id}` | Detailed metadata & orbital elements |
| `POST` | `/api/predict` | Instantaneous state vector $(\vec{r}, \vec{v}, \vec{a})$ prediction |
| `GET` | `/api/criticality/ranking` | Ranked priority queue of highest-hazard debris |
| `POST` | `/api/fleet/optimize` | Solves for minimum robot fleet size $K_{\text{min}}$ & VRP tours |
| `POST` | `/api/j2_drift/optimize` | Computes optimal drift orbit and fuel savings |
| `POST` | `/api/reentry/aerothermal` | Multi-material reentry demise & ablation analysis |
| `POST` | `/api/reentry/point_nemo` | Point Nemo retro-burn & 3-Sigma dispersion ellipse |
| `POST` | `/api/kessler/simulate` | 30-year Kessler cascade population simulator |
| `WS` | `/ws/telemetry` | Real-time WebSocket streaming of orbital positions |
