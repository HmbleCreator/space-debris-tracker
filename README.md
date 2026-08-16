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

## 📚 1. Literature Scenario Comparisons

Comparisons against published study parameters and qualitative findings from aerospace literature:

| Literature Source | Scenario / Target | Published Literature Sizing / Finding | AETHERIS-ADR Implementation | Comparative Finding / Interpretation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Biesbroek et al. (2013)** (*6th European Conf. on Space Debris*) | 8-tonne class SSO target (~800 km, ~98.5°) | Servicer sized with **$709\text{--}784\text{ kg}$** dry mass and **$810\text{--}878\text{ kg}$** propellant | Theoretical Hohmann retro-burn: **$\Delta v = 201.45\text{ m/s}$** | The calculated theoretical Hohmann deorbit $\Delta v$ represents the disposal phase minimum. Full mission studies (such as e.Deorbit) dimension ~810–878 kg propellant to cover rendezvous, capture proximity ops, disposal retro-burn, and flight margins. | **CONSISTENT** |
| **Bombardelli & Peláez (2011) Section V** | 5-ton ($5000\text{ kg}$) object ($1000\text{ km} \to 300\text{ km}, 70\text{ mN}$ net) | Qualitatively bounds deorbit time: **"in less than one year"** | **$310.5\text{ days}$** ($0.85\text{ years}$) | Predicted continuous transfer duration satisfies the published upper bound of $< 1\text{ year}$. | **CONSISTENT** |
| **Castronuovo (2011) *Acta Astronautica*** (DOI: 10.1016/j.actaastro.2011.04.017) | Multi-target Sun-synchronous cluster (41 rocket bodies, 800–1000 km, ~98°) | Multi-target campaign targeting ~5 SSO objects/year via orbital perturbation drift | Multi-target perturbation drift optimizer ($J_2$ differential drift) | Demonstrates the same qualitative campaign strategy (exploiting $J_2$ nodal precession over multi-week drift arcs to avoid prohibitive out-of-plane $\Delta v$), achieving $>75\text{--}81\%$ savings across representative SSO and high-inclination clusters. | **CONSISTENT** |

> **Parameter Specificity Note on Propellant Savings**: Propellant savings from $J_2$ differential nodal drift depend strongly on target inclination and RAAN separation. For representative retrograde Sun-synchronous pairs ($800\text{ km}, 98.5^\circ, \Delta \Omega = 5^\circ$), savings exceed $75\%$; for high-inclination prograde pairs ($840\text{ km}, 71.0^\circ, \Delta \Omega = 12.5^\circ$), savings exceed $81\%$, saving $> 1200\text{ m/s}$ compared to direct impulsive plane changes.

## ⚙️ 2. Internal Formula Verifications & Conservation Checks

Automated unit tests validating that our codebase correctly executes mathematical derivations:

| Verification Target | Physics / Governing Equation | Test Condition | Model Implementation Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Secondary Formation Equilibrium (Eq. 5)** | $F_{p2} = F_{p1} \left( 1 + \eta_t \frac{m_{\text{IBS}}}{m_d} \right)$ | $m_{\text{IBS}} = 500\text{ kg}, m_d = 1000\text{ kg}, F_{p1} = 200\text{ mN}$ | $F_{p2} = 300\text{ mN} \implies a_{\text{IBS}} = a_d = 1.0 \times 10^{-4}\text{ m/s}^2$ | **VERIFIED (0.00% Formation Drift)** |
| **Two-Body Vis-Viva Integration** | $v = \sqrt{\mu \left(\frac{2}{r} - \frac{1}{a}\right)}$ | Circular $768\text{ km}$ to $45\text{ km}$ perigee | $\Delta v_{\text{retro}} = 201.45\text{ m/s}$ | **VERIFIED** |
| **Continuous Tangential Spiral $\Delta v$** | $\Delta v = \|v(r_2) - v(r_1)\|$ | Circular $1000\text{ km}$ to $300\text{ km}$ | $\Delta v = 375.62\text{ m/s}$ | **VERIFIED** |
| **$J_2$ Secular Nodal Drift Rate** | $\dot{\Omega} = -\frac{3}{2} J_2 \left(\frac{R_E}{p}\right)^2 \bar{n} \cos i$ | Circular $840\text{ km}, 71.0^\circ$ | $\dot{\Omega} = -2.104^\circ/\text{day}$ | **VERIFIED** |

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
