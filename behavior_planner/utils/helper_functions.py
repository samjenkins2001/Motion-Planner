__author__ = "Luca Troncone, Rainer Trauth"
__copyright__ = "TUM Institute of Automotive Technology"
__version__ = "1.0"
__maintainer__ = "Rainer Trauth"
__email__ = "rainer.trauth@tum.de"
__status__ = "Beta"

import numpy as np
from shapely.geometry import LineString, Point

# commonroad imports
from commonroad.geometry.shape import Rectangle
from commonroad.scenario.traffic_sign_interpreter import TrafficSignInterpreter
from commonroad.scenario.lanelet import LaneletType
from commonroad.scenario.traffic_sign import SupportedTrafficSignCountry

from commonroad_dc.geometry.util import resample_polyline
from cr_scenario_handler.utils.utils_coordinate_system import smooth_ref_path


def get_remaining_path(ego_state, ref_path):
    point_, index = find_nearest_point_to_path(ref_path, ego_state.position)
    ref_path = ref_path[index:]
    return ref_path


def sort_by_distance(ego_state, objects):
    obj_sorted = sorted(objects, key=lambda x: distance(ego_state.position, x.initial_state.position))
    return obj_sorted


def calc_remaining_time_steps(ego_state_time: float, t: float, planning_problem, dt: float):
    """
    Get the minimum and maximum amount of remaining time steps.

    Args:
        ego_state_time (float): Current time of the state of the ego vehicle.
        t (float): Checked time.
        planning_problem (PlanningProblem): Considered planning problem.
        dt (float): Time step size of the scenario.

    Returns:
        int: Minimum remaining time steps.
        int: Maximum remaining time steps.
    """
    considered_time_step = int(ego_state_time + t / dt)
    if hasattr(planning_problem.goal.state_list[0], "time_step"):
        min_remaining_time = (
                planning_problem.goal.state_list[0].time_step.start - considered_time_step
        )
        max_remaining_time = (
                planning_problem.goal.state_list[0].time_step.end - considered_time_step
        )
        return min_remaining_time, max_remaining_time
    else:
        return False


def distance(pos1: np.array, pos2: np.array):
    """
    Return the euclidean distance between 2 points.

    Args:
        pos1 (np.array): First point.
        pos2 (np.array): Second point.

    Returns:
        float: Distance between point 1 and point 2.
    """
    return np.linalg.norm(pos1 - pos2)


def dist_to_nearest_point(center_vertices: np.ndarray, pos: np.array):
    """
    Find the closest distance of a given position to a polyline.

    Args:
        center_vertices (np.ndarray): Considered polyline.
        pos (np.array): Considered position.

    Returns:
        float: Closest distance between the polyline and the position.
    """
    # create a point and a line, project the point on the line and find the nearest point
    # shapely used
    point = Point(pos)
    linestring = LineString(center_vertices)
    project = linestring.project(point)
    nearest_point = linestring.interpolate(project)

    return distance(pos, np.array([nearest_point.x, nearest_point.y])), [nearest_point.x, nearest_point.y]


def find_nearest_point_to_path(center_vertices: np.ndarray, pos: np.array):
    dists = []
    for idx, path in enumerate(center_vertices):
        dists.append(distance(center_vertices[idx], pos))
    index = np.where(dists == min(dists))[0][0]
    return center_vertices[index], index


def get_lanelet_information(scenario, reference_path_ids, ego_state, country: SupportedTrafficSignCountry):
    """Get the current lanelet id, the legal speed limit and the street setting from the CommonRoad scenario

    Args:
        scenario (Scenario): scenario.
        ego_state: ego state
        country (SupportedTrafficSignCountry): country e.g: SupportedTrafficSignCountry.GERMANY)

    Returns:
        int: current_lanelet_id, speed_limit
        str: street setting ('Highway', 'Country', 'Urban')
    """
    traffic_signs = TrafficSignInterpreter(country=country, lanelet_network=scenario.lanelet_network)

    current_position = ego_state.position
    current_lanelets = scenario.lanelet_network.find_lanelet_by_position([current_position])[0]
    current_lanelet = None

    # get legal speed limit
    speed_limit = traffic_signs.speed_limit(lanelet_ids=frozenset(current_lanelets))

    if len(current_lanelets) == 1:
        current_lanelet = current_lanelets[0]
    elif len(current_lanelets) > 1:
        for lanelet_id in current_lanelets:
            if lanelet_id in reference_path_ids:
                current_lanelet = lanelet_id
            else:
                current_lanelet = current_lanelets[0]
    else:
        print("no lanelets detected")

    # check for street setting
    lanelet_type = scenario.lanelet_network.find_lanelet_by_id(current_lanelet).lanelet_type
    if LaneletType('highway') in lanelet_type:
        street_setting = 'Highway'
    elif LaneletType('interstate') in lanelet_type:
        street_setting = 'Highway'
    elif LaneletType('country') in lanelet_type:
        street_setting = 'Country'
    elif LaneletType('urban') in lanelet_type:
        street_setting = 'Urban'
    else:  # default is urban
        street_setting = 'Urban'

    if scenario.scenario_id.map_name == 'US101':  # only highway scenarios
        street_setting = 'Highway'

    return current_lanelet, speed_limit, street_setting


def find_country_traffic_sign_id(scenario):
    """finds corresponding SupportedTrafficSignCountry as defined in scenario

    Args:
        scenario (Scenario): scenario.

    Returns:
        SupportedTrafficSignCountry
    """

    country_id = scenario.scenario_id.country_id

    if country_id == 'DEU':
        return SupportedTrafficSignCountry.GERMANY
    elif country_id == 'USA':
        return SupportedTrafficSignCountry.USA
    elif country_id == 'CHN':
        return SupportedTrafficSignCountry.CHINA
    elif country_id == 'ESP':
        return SupportedTrafficSignCountry.SPAIN
    elif country_id == 'RUS':
        return SupportedTrafficSignCountry.RUSSIA
    elif country_id == 'ARG':
        return SupportedTrafficSignCountry.ARGENTINA
    elif country_id == 'BEL':
        return SupportedTrafficSignCountry.BELGIUM
    elif country_id == 'FRA':
        return SupportedTrafficSignCountry.FRANCE
    elif country_id == 'GRC':
        return SupportedTrafficSignCountry.GREECE
    elif country_id == 'HRV':
        return SupportedTrafficSignCountry.CROATIA
    elif country_id == 'ITA':
        return SupportedTrafficSignCountry.ITALY
    elif country_id == 'PRI':
        return SupportedTrafficSignCountry.PUERTO_RICO
    elif country_id == 'ZAM':
        return SupportedTrafficSignCountry.ZAMUNDA
    else:
        return None


def get_closest_preceding_obstacle(predictions, lanelet_network, coordinate_system, lanelet_id, ego_position_s,
                                   ego_state):
    obstacles_on_lanelet = get_predicted_obstacles_on_lanelet(predictions, lanelet_network, lanelet_id,
                                                              search_by_shape=False)
    closest_obstacle = None
    closest_obstacle_pos_s = None
    for obstacle_id in obstacles_on_lanelet:
        obstacle = obstacles_on_lanelet.get(obstacle_id)
        obstacle_position_xy = obstacle.get('pos_list')[0]
        try:
            obstacle_position_s = coordinate_system.convert_to_curvilinear_coords(obstacle_position_xy[0],
                                                                                  obstacle_position_xy[1])[0]
        except:
            print("VP object out of projection domain. Object position: ", obstacle_position_xy)
            continue

        if obstacle_position_s > ego_position_s:
            if closest_obstacle is None:
                closest_obstacle = obstacle
                closest_obstacle_pos_s = obstacle_position_s
            else:
                if obstacle_position_s < closest_obstacle_pos_s:
                    closest_obstacle = obstacle
                    closest_obstacle_pos_s = obstacle_position_s

    if closest_obstacle is not None:
        dist_preceding_veh = distance(ego_state.position, closest_obstacle.get('pos_list')[0])
        vel_preceding_veh = closest_obstacle.get('v_list')[0]
    else:
        dist_preceding_veh = None
        vel_preceding_veh = None

    return closest_obstacle, dist_preceding_veh, vel_preceding_veh


def get_predicted_obstacles_on_lanelet(predictions, lanelet_network, lanelet_id, search_point=None,
                                       search_distance=None, search_by_shape=False):  # add config search by shape
    lanelet_ids = create_consecutive_lanelet_id_list(lanelet_network, lanelet_id)
    obstacles_on_lanelet = dict()
    for obstacle_id in predictions:
        obstacle_position = predictions.get(obstacle_id).get('pos_list')[0]
        if search_by_shape:
            obstacle_orientation = predictions.get(obstacle_id).get('orientation_list')[0]
            obstacle_length = predictions.get(obstacle_id).get('shape').get('length')
            obstacle_width = predictions.get(obstacle_id).get('shape').get('width')
            obstacle_shape = Rectangle(length=obstacle_length * 2, width=obstacle_width * 0.2, center=obstacle_position,
                                       orientation=obstacle_orientation)
            obstacle_lanelet_ids = lanelet_network.find_lanelet_by_shape(obstacle_shape)
        else:
            obstacle_lanelet_ids = lanelet_network.find_lanelet_by_position([obstacle_position])[0]
        if search_point is None:
            for obstacle_lanelet_id in obstacle_lanelet_ids:
                if obstacle_lanelet_id in lanelet_ids:
                    obstacles_on_lanelet[obstacle_id] = predictions.get(obstacle_id)
        else:
            for obstacle_lanelet_id in obstacle_lanelet_ids:
                if obstacle_lanelet_id in lanelet_ids:
                    obstacle_distance = distance(search_point, obstacle_position)
                    if obstacle_distance <= search_distance:
                        obstacles_on_lanelet[obstacle_id] = predictions.get(obstacle_id)

    return obstacles_on_lanelet


def create_consecutive_lanelet_id_list(lanelet_network, start_lanelet_id, navigation_route_ids=None):
    """creates a list of lanelet_ids that are the basis for the reference path
    TODO: deal with loops in the lanelet network
    TODO: plan route further than navigation route

    :param lanelet_network: scenario.lanelet_network
    :param start_lanelet_id: lanelet_id of initial state
    :param navigation_route_ids: lanelet ids of existing route, if available

    :return: list of lanelet_ids"""
    consecutive_lanelet_ids = [start_lanelet_id]

    # successors
    end = False
    while not end:
        lanelet = lanelet_network.find_lanelet_by_id(consecutive_lanelet_ids[-1])
        if lanelet.successor:
            # avoid duplicate lanelets from circles in lanelet_network
            unique_lanelet_ids, counts = np.unique(consecutive_lanelet_ids, return_counts=True)
            counts_dict = dict(zip(unique_lanelet_ids, counts))

            if navigation_route_ids is not None:
                for successor in lanelet.successor:
                    if ((successor in navigation_route_ids)
                            and (counts_dict.get(successor) is None)):
                        consecutive_lanelet_ids += [successor]
                        end = True
                        break
                end = not end
            else:
                for successor in lanelet.successor:
                    if counts_dict.get(successor) is None:
                        consecutive_lanelet_ids += [successor]
                        end = True
                        break
                end = not end
        else:
            end = True
    return consecutive_lanelet_ids


def retrieve_glb_nav_path_lane_changes(route):
    # TODO: get lane changes
    # lane_changes = route._compute_lane_change_instructions()
    lane_changes = []
    return lane_changes


def compute_straight_reference_path(lanelet_network, list_ids_lanelets, point_dist: float = 0.125):
    """Computes a straight reference path given the list of portions of each lanelet

    lanelet_network (LaneletNetwork): lanelet_network of scenario
    list_ids_lanelets (List(int)): list of lanelet ids
    """
    straight_reference_path = None
    for lanelet_id in list_ids_lanelets:
        lanelet = lanelet_network.find_lanelet_by_id(lanelet_id)
        if straight_reference_path is None:
            straight_reference_path = lanelet.center_vertices
        else:
            straight_reference_path = np.concatenate((straight_reference_path, lanelet.center_vertices), axis=0)

    return resample_polyline(straight_reference_path, point_dist)  # TODO get step size via config


def optimize_reference_path(lanelet_network, straight_reference_path, goal_polygons=None, goal_lanelet_ids=None,
                            additional_meters: int = 5, point_dist: float = 0.125):
    """Optimizes the reference_path

    ensures that the reference path passes through a goal polygon
    smooths the reference path
    adds five meters to the beginning and end of the reference path

    :param straight_reference_path: array containing the coordinates of the reference path.
    :param goal_polygons: array containing the polygons of the goal area.
    :param goal_lanelet_ids: array containing the lanelet ids of the goal area.
    :param additional_meters: meters that will be added to the beginning and end of the reference path.
    :param point_dist: desired distance between the reference path points
    :return: array containing the coordinates of the optimized reference path.

    """
    # TODO ensure that the reference path passes through a goal polygon
    if goal_polygons is not None:

        # check if the reference path intersects the goal area
        meters_in_goal = 0
        for polygon in goal_polygons:
            previous_coordinate = straight_reference_path[0]
            for coordinate in straight_reference_path[1:]:
                if polygon.contains_point(coordinate):
                    meters_in_goal += np.linalg.norm(previous_coordinate, coordinate)
                previous_coordinate = coordinate

        # check if goal position is defined by lanelets
        if goal_lanelet_ids is not None and len(goal_lanelet_ids) > 0:
            goal_lanelets = []
            for lanelet_id in goal_lanelet_ids:
                goal_lanelets.append(lanelet_network.find_lanelet_by_id(lanelet_id))

    # smooths the reference path
    reference_path = smooth_reference_path(straight_reference_path)

    # adds five meters to the beginning and end of the reference path
    extension_vector_beginning = np.array([reference_path[0][0] - reference_path[1][0],
                                           reference_path[0][1] - reference_path[1][1]])
    extended_beginning_point = np.array([reference_path[0] +
                                         (additional_meters / np.linalg.norm(
                                             extension_vector_beginning)) * extension_vector_beginning])

    extension_vector_end = np.array([reference_path[-1][0] - reference_path[-2][0],
                                     reference_path[-1][1] - reference_path[-2][1]])
    extended_end_point = np.array([reference_path[-1] +
                                   (additional_meters / np.linalg.norm(
                                       extension_vector_end)) * extension_vector_end])

    reference_path = np.concatenate((extended_beginning_point, reference_path, extended_end_point))

    # set desired distance between points
    reference_path = resample_polyline(reference_path, point_dist)

    return reference_path


def smooth_reference_path(reference_path):
    """
    smooth the reference path

    :param reference_path: array containing the coordinates of the reference path.
    :return: array containing the coordinates of the smoothed reference path.
    """
    # hard-coded so that the smoothing works consistently
    reference_path_resampled = resample_polyline(reference_path, 0.125)

    # smooth the reference path
    reference_path_smooth = smooth_ref_path(reference_path_resampled)

    return reference_path_smooth
