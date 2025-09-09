from dataclasses import dataclass

import openrouteservice


@dataclass
class ORSSettings:
    # For future reference maybe check this suggestion: https://gitlab.heigit.org/climate-action/plugins/walkability/-/merge_requests/82#note_61406
    client: openrouteservice.Client

    snapping_rate_limit: int = 100
    snapping_request_size_limit: int = 4999

    directions_rate_limit: int = 40
    directions_waypoint_limit: int = 50

    coordinate_precision: float = 0.000001
    isochrone_max_batch_size: int = 5
