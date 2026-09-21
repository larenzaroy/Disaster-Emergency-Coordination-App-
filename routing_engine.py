"""
Smart Ambulance Routing & Traffic Signal Green Corridor Preemption Engine.
Calculates optimal paths, waypoints, ETA, and preempts traffic signals to create an unobstructed Green Corridor.
"""

import math

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_interpolated_route(start_lat, start_lon, end_lat, end_lon, steps=15):
    """
    Generates realistic road-like waypoint polyline between two coordinates.
    Adds slight city-grid jogs to simulate street routing.
    """
    waypoints = []
    mid_lat = (start_lat + end_lat) / 2.0
    mid_lon = (start_lon + end_lon) / 2.0

    # Intermediate intersection dogleg
    turn_lat = start_lat + (end_lat - start_lat) * 0.45
    turn_lon = start_lon + (end_lon - start_lon) * 0.55

    for i in range(steps + 1):
        t = i / float(steps)
        if t <= 0.5:
            # Segment 1: Start to turn point
            sub_t = t * 2.0
            cur_lat = start_lat + (turn_lat - start_lat) * sub_t
            cur_lon = start_lon + (turn_lon - start_lon) * sub_t
        else:
            # Segment 2: Turn point to destination
            sub_t = (t - 0.5) * 2.0
            cur_lat = turn_lat + (end_lat - turn_lat) * sub_t
            cur_lon = turn_lon + (end_lon - turn_lon) * sub_t
        waypoints.append([round(cur_lat, 6), round(cur_lon, 6)])

    return waypoints

def compute_green_corridor(ambulance_pos, route_waypoints, traffic_signals, corridor_radius_km=1.2):
    """
    Determines which traffic signals along the route need to be preempted to GREEN.
    Returns the updated signals state and the time savings achieved.
    """
    preempted_signals = []
    amb_lat, amb_lon = ambulance_pos

    for sig in traffic_signals:
        sig_lat = sig["latitude"]
        sig_lon = sig["longitude"]

        # Check distance to ambulance
        dist_to_amb = haversine_km(amb_lat, amb_lon, sig_lat, sig_lon)

        # Check proximity to any route waypoint
        min_dist_to_route = min([haversine_km(w[0], w[1], sig_lat, sig_lon) for w in route_waypoints]) if route_waypoints else 999.0

        is_preempted = False
        if min_dist_to_route < 0.8:  # Signal is right along the ambulance route
            is_preempted = True
            preempted_signals.append({
                "id": sig["id"],
                "name": sig["intersection_name"],
                "lat": sig_lat,
                "lon": sig_lon,
                "status": "GREEN_CORRIDOR_ACTIVE",
                "distance_to_amb_km": round(dist_to_amb, 2),
                "cleared": True
            })

    total_route_km = 0.0
    for i in range(len(route_waypoints) - 1):
        total_route_km += haversine_km(
            route_waypoints[i][0], route_waypoints[i][1],
            route_waypoints[i+1][0], route_waypoints[i+1][1]
        )

    # Speed metrics
    normal_city_speed_kmh = 28.0  # congested city traffic with red stops
    green_corridor_speed_kmh = 58.0  # cleared corridor with priority signals

    normal_eta_mins = (total_route_km / normal_city_speed_kmh) * 60.0 + (len(preempted_signals) * 1.5)
    priority_eta_mins = (total_route_km / green_corridor_speed_kmh) * 60.0
    mins_saved = max(1.0, normal_eta_mins - priority_eta_mins)

    return {
        "total_distance_km": round(total_route_km, 2),
        "normal_eta_mins": round(normal_eta_mins, 1),
        "priority_eta_mins": round(priority_eta_mins, 1),
        "minutes_saved": round(mins_saved, 1),
        "preempted_signals_count": len(preempted_signals),
        "signals": preempted_signals
    }
