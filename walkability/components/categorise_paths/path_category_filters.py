from typing import Dict

from walkability.components.utils.misc import safe_string_to_float


class PathCategoryFilters:
    # TODO instantiating this class over and over for filtering in an apply is a bad idea, think about how to store the necessary data without re-instantiating it on every check
    def __init__(self, tags: dict, speed_category_max: Dict[str, float] = None):
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

        self.max_speed = PathCategoryFilters.extract_speed(tags=tags)

        self.speed_category_max = speed_category_max or {'slow': 10, 'medium': 30, 'fast': 50}

    @staticmethod
    def extract_speed(tags: dict) -> float:
        maxspeed_zone = PathCategoryFilters._parse_maxspeed_zone(tags)

        potential_speeds = [
            tags.get('maxspeed'),
            tags.get('maxspeed:forward'),
            tags.get('maxspeed:backward'),
            maxspeed_zone,
        ]
        speeds = [safe_string_to_float(speed) for speed in potential_speeds]
        return max(speeds)

    @staticmethod
    def _parse_maxspeed_zone(tags: dict) -> float | str:
        zone_string = tags.get('zone:maxspeed') or tags.get('zone:traffic') or ''
        zone_split = zone_string.split(':', 1)
        zone_split.reverse()
        zone_info = zone_split[0]
        country = zone_split[1] if len(zone_split) == 2 else ''

        match zone_info:
            case 'urban':
                if country in ['BQ-SE', 'BQ-BO', 'CW']:
                    maxspeed_zone = 40
                elif country in ['BE-BRU', 'BQ-SA', 'SX']:
                    maxspeed_zone = 30
                else:
                    maxspeed_zone = 50
            case 'rural':
                if country in ['DE']:
                    maxspeed_zone = 100
                elif country in ['LU', 'BE-WAL']:
                    maxspeed_zone = 90
                elif country in ['NL', 'FR', 'AW']:
                    maxspeed_zone = 80
                elif country in ['BE-VLG', 'BE-BRU']:
                    maxspeed_zone = 70
                elif country in ['BQ-SA', 'BQ-SE', 'BQ-BO', 'CW']:
                    maxspeed_zone = 60
                elif country in ['SX']:
                    maxspeed_zone = 50
                else:
                    maxspeed_zone = 70
            case 'school':
                maxspeed_zone = 50
            case 'motorway':
                maxspeed_zone = 120
            case _:
                maxspeed_zone = zone_info

        return maxspeed_zone

    def _potential(self, d: Dict) -> bool:
        return d.get('highway') in self._potential_highway_values_all or d.get('route') == 'ferry'

    # Exclusive: Only for pedestrians
    def _potentially_exclusive(self, d: Dict) -> bool:
        return (
            (
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
                        and d.get('footway') not in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                    )
                )
            )
            and d.get('motor_vehicle') != 'yes'
            and d.get('vehicle') != 'yes'
        )

    def _shared_with_bikes(self, d: Dict) -> bool:
        return d.get('bicycle') in ['yes', 'designated', 'permissive', 'official'] and (d.get('segregated') != 'yes')

    def _designated_foot(self, d: Dict) -> bool:
        return d.get('foot') in ['yes', 'permissive', 'designated', 'official'] and self.max_speed == -1

    def _potentially_separated(self, d: Dict) -> bool:
        return (
            d.get('highway') in ['footway', 'path', 'cycleway']
            and (self._designated_foot(d) or d.get('footway') in ['sidewalk', 'crossing', 'traffic_island', 'yes'])
        ) or (self._potential(d) and self._designated_foot(d))

    @staticmethod
    def has_sidewalk(d: Dict) -> bool:
        return (
            d.get('sidewalk') in ['both', 'left', 'right', 'yes', 'lane']
            or d.get('sidewalk:left') == 'yes'
            or d.get('sidewalk:right') == 'yes'
            or d.get('sidewalk:both') == 'yes'
        )

    @staticmethod
    def has_no_sidewalk(d: Dict):
        return (
            d.get('sidewalk') == 'no'
            or d.get('sidewalk:both') == 'no'
            or (d.get('sidewalk:left') == 'no' and d.get('sidewalk:right') == 'no')
            or d.get('sidewalk') == 'none'
            or d.get('sidewalk:both') == 'none'
            or (d.get('sidewalk:left') == 'none' and d.get('sidewalk:right') == 'none')
        )

    @staticmethod
    def sidewalk_is_separate(d: Dict):
        return (
            d.get('sidewalk') == 'separate'
            or d.get('sidewalk:both') == 'separate'
            or (d.get('sidewalk:left') == 'separate' and d.get('sidewalk:right') == 'separate')
        )

    def designated(self, d: Dict) -> bool:
        return (
            (self._potentially_exclusive(d) or self._potentially_separated(d)) and not self._shared_with_bikes(d)
        ) or (self._potential(d) and PathCategoryFilters.has_sidewalk(d))

    def designated_shared_with_bikes(self, d: Dict) -> bool:
        return (
            (self._potentially_exclusive(d) or self._potentially_separated(d)) and self._shared_with_bikes(d)
        ) or d.get('highway') == 'path'

    def shared_with_low_speed(self, d: Dict) -> bool:
        return (
            d.get('highway') in self._potential_highway_values_low_speed
            and self.max_speed <= self.speed_category_max.get('slow')
            or 0 < self.max_speed <= self.speed_category_max.get('slow')
        )

    def shared_with_medium_speed(self, d: Dict) -> bool:
        return (
            d.get('highway') == 'track'
            and (
                self.speed_category_max.get('slow') < self.max_speed <= self.speed_category_max.get('medium')
                or self.max_speed == -1
            )
        ) or (self.speed_category_max.get('slow') < self.max_speed <= self.speed_category_max.get('medium'))

    def shared_with_high_speed(self, d: Dict) -> bool:
        return self.speed_category_max.get('medium') < self.max_speed <= self.speed_category_max.get('fast')

    def shared_with_very_high_speed(self, d: Dict) -> bool:
        return self.max_speed > self.speed_category_max.get('fast')

    def shared_with_unknown_speed(self, d: Dict) -> bool:
        return self._potential(d) and PathCategoryFilters.has_no_sidewalk(d) and self.max_speed == -1

    # For documentation:
    # ignored primary tags = 'highway in (motorway,trunk,motorway_link,trunk_link,primary_link,secondary_link,tertiary_link,bus_guideway,escape,raceway,busway,bridleway,via_ferrata,cycleway)'
    # ignored secondary tags = 'sidewalk=no'
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
            or PathCategoryFilters.sidewalk_is_separate(d=d)
            or d.get('footway') == 'no'
            or d.get('access') in ['no', 'private', 'permit', 'military', 'delivery', 'customers']
            or d.get('foot') in ['no', 'private', 'use_sidepath', 'discouraged', 'destination']
            or (d.get('highway') == 'service' and d.get('bus') in ['designated', 'yes'])
            or d.get('ford') == 'yes'
        )
