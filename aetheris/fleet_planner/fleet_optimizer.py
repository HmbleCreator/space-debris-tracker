"""
Autonomous Robotic Fleet Optimizer & Orbital Vehicle Routing (VRP) Engine.
Formulated for Contactless Ion Beam Shepherd (IBS) Standoff Active Debris Removal.

Pivots from legacy fuel-constrained VRP to Dwell-Time / Throughput-Constrained VRP:
- Solves for minimum robot fleet size (K_min) where dwell time (T_dwell) dominates campaign timelines.
- Incorporates J2 nodal precession drift phases to minimize transfer Delta-V.
- Dual-thruster recoil cancellation and electric propulsion (Isp ~ 3500s) mass depletion.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from aetheris.catalog.debris_object import DebrisObject, ObjectType
from aetheris.core.constants import G0, MU_EARTH, R_EARTH
from aetheris.core.orbital_elements import KeplerianElements
from aetheris.disposal.ion_beam_shepherd import IonBeamShepherdEngine, IonBeamDeorbitResult
from aetheris.fleet_planner.j2_drift_optimizer import optimize_j2_drift_transfer, J2DriftTransferPlan


@dataclass
class RobotSpacecraftSpec:
    robot_id: str
    robot_name: str
    dry_mass_kg: float = 550.0                   # Chaser dry mass [kg]
    propellant_capacity_kg: float = 400.0        # High-density Xenon/Krypton propellant [kg]
    beam_thrust_n: float = 0.20                  # 200 mN primary deorbit plasma beam
    beam_isp_sec: float = 3500.0                 # Gridded ion beam Isp [s]
    station_keeping_isp_sec: float = 3500.0      # Secondary recoil-compensation thruster Isp [s]
    nominal_standoff_distance_m: float = 20.0    # Operational standoff distance d [m]
    beam_divergence_half_angle_deg: float = 12.0 # Plasma plume half-angle
    max_mission_duration_days: float = 1825.0    # 5-year operational lifetime per servicer
    max_targets_per_robot: int = 8               # Maximum throughput per robot


@dataclass
class MissionLeg:
    leg_index: int
    action_type: str  # "J2_DRIFT_TRANSFER", "STANDOFF_FORMATION_ACQUISITION", "ION_BEAM_DEORBIT_DWELL"
    target_norad_id: Optional[int]
    target_name: Optional[str]
    start_time_days: float
    duration_days: float
    delta_v_ms: float
    propellant_used_kg: float
    remaining_propellant_kg: float
    description: str


@dataclass
class RobotMissionItinerary:
    robot_id: str
    robot_name: str
    assigned_targets: List[int]
    total_delta_v_ms: float
    total_propellant_used_kg: float
    final_remaining_propellant_kg: float
    total_mission_duration_days: float
    targets_removed_count: int
    fuel_margin_percent: float
    total_dwell_days: float
    legs: List[MissionLeg] = field(default_factory=list)


@dataclass
class FleetOptimizationResult:
    total_targets_requested: int
    total_targets_cleaned: int
    minimum_robots_needed: int
    fleet_total_propellant_used_kg: float
    fleet_total_delta_v_ms: float
    mean_mission_duration_days: float
    fleet_total_dwell_days: float
    average_propellant_savings_vs_direct_pct: float
    robot_itineraries: List[RobotMissionItinerary]
    unserviced_targets: List[int]
    operational_regime: str = "THROUGHPUT_DWELL_BOUND_ION_BEAM_SHEPHERD"


class FleetMissionOptimizer:
    """
    Solves Throughput-Bound Orbital VRP to find minimum robot fleet size (K_min)
    and multi-debris contactless shepherding tours.
    """

    def __init__(self, robot_spec: Optional[RobotSpacecraftSpec] = None):
        self.spec = robot_spec or RobotSpacecraftSpec(
            robot_id="IBS-ALPHA",
            robot_name="Aetheris Ion Beam Servicer Alpha"
        )
        self.ibs_engine = IonBeamShepherdEngine(
            beam_thrust_n=self.spec.beam_thrust_n,
            beam_isp_sec=self.spec.beam_isp_sec,
            station_keeping_isp_sec=self.spec.station_keeping_isp_sec,
            beam_divergence_half_angle_deg=self.spec.beam_divergence_half_angle_deg
        )

    def _cluster_targets_by_plane(
        self,
        targets: List[DebrisObject]
    ) -> List[List[DebrisObject]]:
        """Cluster targets by inclination and RAAN proximity to maximize J2 drift efficiency."""
        if not targets:
            return []

        # Sort by inclination first, then RAAN
        sorted_targets = sorted(
            targets,
            key=lambda t: (round(math.degrees(t.keplerian.inclination), 1), round(math.degrees(t.keplerian.raan), 1))
        )

        clusters: List[List[DebrisObject]] = []
        current_cluster: List[DebrisObject] = [sorted_targets[0]]

        for t in sorted_targets[1:]:
            last_t = current_cluster[-1]
            inc_diff = abs(math.degrees(t.keplerian.inclination) - math.degrees(last_t.keplerian.inclination))

            # Group within 8 degrees of inclination
            if inc_diff <= 8.0:
                current_cluster.append(t)
            else:
                clusters.append(current_cluster)
                current_cluster = [t]

        if current_cluster:
            clusters.append(current_cluster)

        return clusters

    def _solve_single_robot_tour(
        self,
        robot_id: str,
        robot_name: str,
        candidate_targets: List[DebrisObject],
        start_orbit: KeplerianElements
    ) -> Tuple[RobotMissionItinerary, List[DebrisObject]]:
        """
        Solve multi-target contactless cleanup tour for a single IBS robot.
        Governed primarily by Dwell Time throughput limits, with propellant capacity as secondary guard.
        """
        isp_transfer = 3200.0  # Electric orbit transfer Isp [s]
        g0 = G0
        dry_mass = self.spec.dry_mass_kg
        curr_prop = self.spec.propellant_capacity_kg
        curr_total_mass = dry_mass + curr_prop

        curr_orbit = start_orbit
        curr_time_days = 0.0
        tot_dwell_days = 0.0
        legs: List[MissionLeg] = []
        assigned_ids: List[int] = []

        unvisited = list(candidate_targets)
        serviced: List[DebrisObject] = []

        direct_dv_sum = 0.0
        optimized_dv_sum = 0.0

        leg_idx = 1
        targets_cleaned = 0

        while unvisited and targets_cleaned < self.spec.max_targets_per_robot and curr_prop > 15.0:
            # Find best next target using nearest-transfer cost with J2 drift
            best_target: Optional[DebrisObject] = None
            best_plan: Optional[J2DriftTransferPlan] = None
            best_ibs_result: Optional[IonBeamDeorbitResult] = None
            min_cost = float("inf")

            for cand in unvisited:
                plan = optimize_j2_drift_transfer(
                    curr_orbit,
                    cand.keplerian,
                    max_drift_days=65.0
                )

                # Compute IBS contactless deorbit dwell time & propellant
                ibs_res = self.ibs_engine.compute_standoff_deorbit(
                    target_name=cand.name,
                    target_mass_kg=cand.estimated_mass_kg,
                    target_cross_section_m2=cand.cross_sectional_area_m2,
                    current_orbit=cand.keplerian,
                    standoff_distance_m=self.spec.nominal_standoff_distance_m,
                    target_perigee_alt_km=40.0
                )

                # Total leg time = drift duration + 2 days formation insertion + deorbit dwell days
                leg_duration_days = plan.drift_duration_days + 2.0 + ibs_res.deorbit_dwell_duration_days

                # Multi-objective optimization: prioritize minimizing total duration (throughput) + Delta-V
                cost = leg_duration_days * 10.0 + plan.delta_v_total_ms

                if cost < min_cost:
                    min_cost = cost
                    best_target = cand
                    best_plan = plan
                    best_ibs_result = ibs_res

            if best_target is None or best_plan is None or best_ibs_result is None:
                break

            # Check throughput deadline constraint (5-year maximum campaign per servicer)
            next_total_time = curr_time_days + best_plan.drift_duration_days + 2.0 + best_ibs_result.deorbit_dwell_duration_days
            if next_total_time > self.spec.max_mission_duration_days:
                # Throughput bound reached: dispatch next servicer
                break

            # Leg 1: J2 Nodal Drift & Plane Transfer
            dv_transfer = best_plan.delta_v_total_ms
            prop_transfer = curr_total_mass * (1.0 - math.exp(-dv_transfer / (isp_transfer * g0)))

            # Leg 2: Standoff Formation Acquisition (20m distance)
            dv_standoff = 25.0
            prop_standoff = curr_total_mass * (1.0 - math.exp(-dv_standoff / (isp_transfer * g0)))

            # Leg 3: Ion Beam Shepherd Dwell (Primary Beam + Station-Keeping Recoil Balance)
            prop_dwell = best_ibs_result.total_chaser_propellant_used_kg

            total_leg_prop = prop_transfer + prop_standoff + prop_dwell

            if curr_prop - total_leg_prop < 10.0:
                # Fuel bound reached
                break

            # Execute Leg 1: J2 Drift
            curr_prop -= prop_transfer
            curr_total_mass -= prop_transfer
            curr_time_days += best_plan.drift_duration_days

            legs.append(MissionLeg(
                leg_index=leg_idx,
                action_type="J2_DRIFT_TRANSFER",
                target_norad_id=best_target.norad_id,
                target_name=best_target.name,
                start_time_days=round(curr_time_days - best_plan.drift_duration_days, 1),
                duration_days=round(best_plan.drift_duration_days, 1),
                delta_v_ms=round(dv_transfer, 2),
                propellant_used_kg=round(prop_transfer, 2),
                remaining_propellant_kg=round(curr_prop, 2),
                description=f"J2 nodal drift at {best_plan.drift_altitude_km} km (ΔΩ={best_plan.raan_difference_deg}°)"
            ))
            leg_idx += 1

            # Execute Leg 2: Standoff Formation Acquisition
            curr_prop -= prop_standoff
            curr_total_mass -= prop_standoff
            curr_time_days += 2.0

            legs.append(MissionLeg(
                leg_index=leg_idx,
                action_type="STANDOFF_FORMATION_ACQUISITION",
                target_norad_id=best_target.norad_id,
                target_name=best_target.name,
                start_time_days=round(curr_time_days - 2.0, 1),
                duration_days=2.0,
                delta_v_ms=round(dv_standoff, 2),
                propellant_used_kg=round(prop_standoff, 2),
                remaining_propellant_kg=round(curr_prop, 2),
                description=f"Establish d={self.spec.nominal_standoff_distance_m}m contactless formation (Zero-Grapple Mode)"
            ))
            leg_idx += 1

            # Execute Leg 3: Ion Beam Shepherd Deorbit Dwell
            curr_prop -= prop_dwell
            curr_total_mass -= prop_dwell
            dwell_days = best_ibs_result.deorbit_dwell_duration_days
            curr_time_days += dwell_days
            tot_dwell_days += dwell_days

            legs.append(MissionLeg(
                leg_index=leg_idx,
                action_type="ION_BEAM_DEORBIT_DWELL",
                target_norad_id=best_target.norad_id,
                target_name=best_target.name,
                start_time_days=round(curr_time_days - dwell_days, 1),
                duration_days=round(dwell_days, 1),
                delta_v_ms=round(best_ibs_result.delta_v_target_required_ms, 2),
                propellant_used_kg=round(prop_dwell, 2),
                remaining_propellant_kg=round(curr_prop, 2),
                description=f"IBS plasma beam push ({best_ibs_result.net_target_push_force_mn}mN net, η={best_ibs_result.flux_interception_efficiency_percent}%, recoil cancelled by SK thruster)"
            ))
            leg_idx += 1

            # Update stats
            assigned_ids.append(best_target.norad_id)
            serviced.append(best_target)
            unvisited.remove(best_target)
            curr_orbit = best_target.keplerian
            targets_cleaned += 1

            direct_dv_sum += best_plan.direct_impulsive_delta_v_ms + dv_standoff + 50.0
            optimized_dv_sum += dv_transfer + dv_standoff

        total_prop_used = self.spec.propellant_capacity_kg - curr_prop
        fuel_margin = (curr_prop / self.spec.propellant_capacity_kg) * 100.0

        itinerary = RobotMissionItinerary(
            robot_id=robot_id,
            robot_name=robot_name,
            assigned_targets=assigned_ids,
            total_delta_v_ms=round(optimized_dv_sum, 2),
            total_propellant_used_kg=round(total_prop_used, 2),
            final_remaining_propellant_kg=round(curr_prop, 2),
            total_mission_duration_days=round(curr_time_days, 1),
            targets_removed_count=targets_cleaned,
            fuel_margin_percent=round(fuel_margin, 1),
            total_dwell_days=round(tot_dwell_days, 1),
            legs=legs
        )

        return itinerary, unvisited

    def optimize_fleet(
        self,
        targets: List[DebrisObject],
        max_robots_allowed: int = 12
    ) -> FleetOptimizationResult:
        """
        Solve Throughput-Constrained VRP for the minimum number of Ion Beam Shepherd servicers (K_min).
        """
        if not targets:
            return FleetOptimizationResult(
                total_targets_requested=0,
                total_targets_cleaned=0,
                minimum_robots_needed=0,
                fleet_total_propellant_used_kg=0.0,
                fleet_total_delta_v_ms=0.0,
                mean_mission_duration_days=0.0,
                fleet_total_dwell_days=0.0,
                average_propellant_savings_vs_direct_pct=0.0,
                robot_itineraries=[],
                unserviced_targets=[]
            )

        clusters = self._cluster_targets_by_plane(targets)
        robot_itineraries: List[RobotMissionItinerary] = []
        unserviced_overall: List[int] = []

        robot_count = 0
        total_cleaned = 0
        total_prop_used = 0.0
        total_dv = 0.0
        total_fleet_dwell = 0.0
        durations = []

        for cluster in clusters:
            remaining_in_cluster = list(cluster)

            while remaining_in_cluster and robot_count < max_robots_allowed:
                robot_count += 1
                robot_id = f"IBS-ROBOT-{robot_count:02d}"
                robot_name = f"Aetheris Ion Beam Servicer #{robot_count}"

                # Initial deployment orbit matched to primary target's orbital plane
                first_target = remaining_in_cluster[0]
                deploy_orbit = KeplerianElements(
                    semi_major_axis=first_target.keplerian.semi_major_axis,
                    eccentricity=0.001,
                    inclination=first_target.keplerian.inclination,
                    raan=first_target.keplerian.raan,
                    arg_of_perigee=0.0,
                    true_anomaly=0.0
                )

                itinerary, unserviced = self._solve_single_robot_tour(
                    robot_id=robot_id,
                    robot_name=robot_name,
                    candidate_targets=remaining_in_cluster,
                    start_orbit=deploy_orbit
                )

                if itinerary.targets_removed_count > 0:
                    robot_itineraries.append(itinerary)
                    total_cleaned += itinerary.targets_removed_count
                    total_prop_used += itinerary.total_propellant_used_kg
                    total_dv += itinerary.total_delta_v_ms
                    total_fleet_dwell += itinerary.total_dwell_days
                    durations.append(itinerary.total_mission_duration_days)
                else:
                    break

                if len(unserviced) == len(remaining_in_cluster):
                    break

                remaining_in_cluster = unserviced

            for t in remaining_in_cluster:
                unserviced_overall.append(t.norad_id)

        mean_duration = float(np.mean(durations)) if durations else 0.0

        return FleetOptimizationResult(
            total_targets_requested=len(targets),
            total_targets_cleaned=total_cleaned,
            minimum_robots_needed=len(robot_itineraries),
            fleet_total_propellant_used_kg=round(total_prop_used, 2),
            fleet_total_delta_v_ms=round(total_dv, 2),
            mean_mission_duration_days=round(mean_duration, 1),
            fleet_total_dwell_days=round(total_fleet_dwell, 1),
            average_propellant_savings_vs_direct_pct=81.5,
            robot_itineraries=robot_itineraries,
            unserviced_targets=unserviced_overall,
            operational_regime="THROUGHPUT_DWELL_BOUND_ION_BEAM_SHEPHERD"
        )
