from pathlib import Path

import geopandas as gpd
from climatoology.base.artifact import _Artifact, ContinuousLegendData, create_geojson_artifact
from climatoology.base.computation import ComputationResources

from walkability.components.utils.misc import generate_colors


def build_network_artifacts(
    connectivity_permeability: gpd.GeoDataFrame, resources: ComputationResources
) -> list[_Artifact]:
    connectivity_artifact = build_connectivity_artifact(connectivity=connectivity_permeability, resources=resources)
    permeability_artifact = build_permeability_artifact(permeability=connectivity_permeability, resources=resources)
    return [connectivity_artifact, permeability_artifact]


def build_connectivity_artifact(
    connectivity: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'coolwarm_r',
) -> _Artifact:
    color = generate_colors(color_by=connectivity.permeability, cmap_name=cmap_name, min=0, max=0)
    legend = ContinuousLegendData(cmap_name=cmap_name, ticks={'High': 1, 'Low': 0})

    return create_geojson_artifact(
        features=connectivity.geometry,
        layer_name='Connectivity',
        filename='connectivity',
        caption=Path('resources/components/network_analyses/connectivity/caption.md').read_text(),
        description=Path('resources/components/network_analyses/connectivity/description.md').read_text(),
        label=connectivity.connectivity.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )


def build_permeability_artifact(
    permeability: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'coolwarm_r',
) -> _Artifact:
    color = generate_colors(color_by=permeability.permeability, cmap_name=cmap_name, min=0, max=0)
    legend = ContinuousLegendData(cmap_name=cmap_name, ticks={'High': 1, 'Low': 0})

    return create_geojson_artifact(
        features=permeability.geometry,
        layer_name='Permeability',
        filename='permeability',
        caption=Path('resources/components/network_analyses/permeability/caption.md').read_text(),
        description=Path('resources/components/network_analyses/permeability/description.md').read_text(),
        label=permeability.permeability.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )
