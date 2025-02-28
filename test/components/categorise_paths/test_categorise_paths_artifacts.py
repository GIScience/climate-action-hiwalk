from approvaltests import verify

from walkability.components.categorise_paths.path_categorisation_artifacts import (
    generate_detailed_pavement_quality_mapping_info,
)


def test_pavement_quality_info_generator():
    verify(generate_detailed_pavement_quality_mapping_info())
