from typing import Dict


class PathCategoryFilters:
    def __init__(self):
        # Potential: potentially walkable features (to be restricted by AND queries)
        self._potential_highway_values = (
            'primary',
            'primary_link',
            'secondary',
            'secondary_link',
            'tertiary',
            'tertiary_link',
            'road',
            'cycleway',
            'unclassified',
            'residential',
            'track',
        )
        self._potential_highway_values_low_speed = (
            'living_street',
            'service',
        )
        self._potential_highway_values_all = self._potential_highway_values + self._potential_highway_values_low_speed

    def _potential(self, d: Dict) -> bool:
        return d.get('highway') in self._potential_highway_values_all or d.get('route') == 'ferry'

    # Exclusive: Only for pedestrians
    def _exclusive(self, d: Dict) -> bool:
        return (
            d.get('highway') in ['steps', 'corridor', 'pedestrian', 'platform']
            or d.get('railway') == 'platform'
            or (
                d.get('highway') == 'path'
                and (
                    d.get('foot') in ['yes', 'designated', 'official']
                    or d.get('footway') in ['access_aisle', 'alley', 'residential', 'link', 'path']
                    or d.get('bicycle') == 'no'
                )
                or (
                    d.get('highway') == 'footway'
                    and d.get('bicycle') != 'yes'
                    and d.get('footway') not in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                )
                and d.get('motor_vehicle') != 'yes'
                and d.get('vehicle') != 'yes'
            )
        ) and d.get('bicycle') not in ['yes', 'designated']

    def _shared_with_bikes(self, d: Dict) -> bool:
        return d.get('bicycle') in ['yes', 'designated'] and (
            d.get('segregated') != 'yes' or d.get('segregated') == 'no'
        )

    def _separated_foot(self, d: Dict) -> bool:
        return d.get('foot') in ['yes', 'permissive', 'designated', 'official'] and d.get('maxspeed') is None

    def _separated(self, d: Dict) -> bool:
        return (
            d.get('highway') == 'footway'
            or (
                d.get('highway') in ['path', 'cycleway']
                and (
                    self._separated_foot(d)
                    or d.get('footway') in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                    or d.get('segregated') == 'yes'
                )
            )
        ) or (
            (self._potential(d))
            and (
                self._separated_foot(d)
                or d.get('sidewalk') in ['both', 'left', 'right', 'yes', 'lane']
                or d.get('sidewalk:left') == 'yes'
                or d.get('sidewalk:right') == 'yes'
                or d.get('sidewalk:both') == 'yes'
            )
        )

    def designated(self, d: Dict) -> bool:
        return (self._exclusive(d) or self._separated(d)) and not self._shared_with_bikes(d)

    def designated_shared_with_bikes(self, d: Dict) -> bool:
        return ((self._exclusive(d) or self._separated(d)) and self._shared_with_bikes(d)) or (
            d.get('highway') in ['path', 'track', 'pedestrian']
            and d.get('motor_vehicle') != 'yes'
            and d.get('vehicle') != 'yes'
            and d.get('segregated') != 'yes'
        )

    def shared_with_low_speed(self, d: Dict) -> bool:
        return d.get('highway') in self._potential_highway_values_low_speed

    def shared_with_medium_speed(self, d: Dict) -> bool:
        return d.get('maxspeed') in ['5', '10', '15', '20', '25', '30'] or d.get('zone:maxspeed') in ['DE:30', '30']

    def shared_with_high_speed(self, d: Dict) -> bool:
        return (
            self._potential(d)
            and (
                d.get('sidewalk') == 'no'
                or d.get('sidewalk:both') == 'no'
                or (d.get('sidewalk:left') == 'no' and d.get('sidewalk:right') == 'no')
                or d.get('sidewalk') == 'none'
                or d.get('sidewalk:both') == 'none'
                or (d.get('sidewalk:left') == 'none' and d.get('sidewalk:right') == 'none')
                or d.get('sidewalk') != '*'
                or d.get('sidewalk:both') != '*'
                or (d.get('sidewalk:left') != '*' and d.get('sidewalk:right') != '*')
            )
            and not (
                d.get('maxspeed') in ['60', '70', '80', '100']
                or d.get('maxspeed:backward') in ['60', '70', '80', '100']
                or d.get('maxspeed:forward') in ['60', '70', '80', '100']
            )
        )

    # For documentation:
    # ignored_primary = 'highway in (motorway,trunk,motorway_link,trunk_link,
    # primary_link,secondary_link,tertiary_link,bus_guideway,escape,raceway,busway,
    # bridleway,via_ferrata,cycleway'
    # ignored_secondary = 'sidewalk=no'
    def inaccessible(self, d: Dict) -> bool:
        return (
            (
                d.get('highway')
                not in [
                    *self._potential_highway_values_all,
                    'pedestrian',
                    'steps',
                    'corridor',
                    'platform',
                    'path',
                    'track',
                    'cycleway',
                    'footway',
                ]
                and d.get('railway') != 'platform'
            )
            or d.get('footway') == 'no'
            or d.get('access') in ['no', 'private', 'permit', 'military', 'delivery', 'customers']
            or d.get('foot') in ['no', 'private', 'use_sidepath', 'discouraged', 'destination']
            or d.get('maxspeed') in ['60', '70', '80', '100']
            or d.get('maxspeed:backward') in ['60', '70', '80', '100']
            or d.get('maxspeed:forward') in ['60', '70', '80', '100']
            or (d.get('highway') == 'service' and d.get('bus') in ['designated', 'yes'])
            or d.get('ford') == 'yes'
        )
