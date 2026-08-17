import logging

from pydantic import Field
from pydantic.dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class POICategory:
    type: str = Field(
        title='POI category type',
        description='Short identifier for the POI category.',
        examples=['education', 'childcare'],
    )
    ohsome_filter: str = Field(
        title='Ohsome filter',
        description='Ohsome filter to query POIs for the category.',
        examples=['amenity=school'],
    )


POI_CATEGORIES = [
    POICategory(type='education', ohsome_filter='amenity=school'),
    POICategory(
        type='childcare',
        ohsome_filter='amenity in (childcare, nursery, kindergarten, toy_library) or leisure in (playground, indoor_play)',
    ),
    POICategory(
        type='healthcare',
        ohsome_filter='amenity in (doctors, clinic, dentist, pharmacy) or healthcare in (doctor, dentist, pharmacy)',
    ),
    POICategory(
        type='everyday needs',
        ohsome_filter=str(
            'amenity in (marketplace, post_office, post_box, atm, bank) '
            'or craft in (shoemaker, tailor, electronics_repair, photographer) '
            'or shop in (supermarket, convenience, cheese, coffee, deli, farm, frozen_food, health_food, organic, '
            'water, bakery, butcher, dairy, food, greengrocer, grocery, seafood, alcohol, beverages, chocolate, '
            'ice_cream, pastry, spices, tea, wine, confectionery, drugstore, chemist, hairdresser, dry_cleaning, '
            'copyshop)'
        ),
    ),
    POICategory(
        type='public transport',
        ohsome_filter='highway=bus_stop or railway in (tram_stop, station, halt, stop) or station=subway',
    ),
    POICategory(
        type='green or natural spaces',
        ohsome_filter=str(
            '(leisure in (garden, nature_reserve, park) or natural in (park, beach) or landuse in (grass, forest)) '
            'and access!=private and access!=no and garden:type!=residential'
        ),
    ),
    POICategory(
        type='culture/leisure',
        ohsome_filter=str(
            'amenity in (cinema, library, public_bookcase, community_centre, planetarium, theatre, arts_centre) '
            'or leisure in (fitness_centre, fitness_station, sports_centre, swimming_pool) '
            'or museum=culture or tourism=museum'
        ),
    ),
    POICategory(
        type='eating out',
        ohsome_filter='amenity in (restaurant, fast_food, food_court, canteen, cafe, pub, bar, biergarten)',
    ),
    POICategory(
        type='pet care & services',
        ohsome_filter=str(
            'amenity=veterinary or leisure=dog_park or (amenity=waste_basket and waste=dog_excrement) '
            'or (amenity=vending_machine and vending=excrement_bags) or shop=pet_grooming'
        ),
    ),
]
