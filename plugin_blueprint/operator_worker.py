# You may ask yourself why this file has such a strange name.
# Well ... python imports: https://discuss.python.org/t/warning-when-importing-a-local-module-with-the-same-name-as-a-2nd-or-3rd-party-module/27799

import geopandas as gpd
import logging
import os
import pandas as pd
import shapely
from PIL import Image
from datetime import datetime
from ohsome import OhsomeClient
from pandas import DataFrame
from pathlib import Path
from pydantic_extra_types.color import Color
from semver import Version
from typing import List, Tuple

from climatoology.base.artifact import create_markdown_artifact, create_table_artifact, create_image_artifact, \
    create_chart_artifact, Chart2dData, ChartType, create_geotiff_artifact, create_geojson_artifact
from climatoology.base.operator import Operator, Info, Concern, ComputationResources, Artifact
from climatoology.utility.api import LulcUtilityUtility, LULCWorkUnit
from plugin_blueprint.input import ComputeInputBlueprint

log = logging.getLogger(__name__)


class OperatorBlueprint(Operator[ComputeInputBlueprint]):
    # This is your working-class hero.
    # See all the details below.

    def __init__(self):
        # Create a base connection for the LULC classification utility.
        # Remove it, if you don't plan on using that utility.
        self.lulc_generator = LulcUtilityUtility(host=os.environ.get('LULC_HOST'),
                                                 port=int(os.environ.get('LULC_PORT')),
                                                 root_url=os.environ.get('LULC_ROOT_URL'))

        # Here is an example for another Utility you can use
        self.ohsome = OhsomeClient(user_agent='CA Plugin Blueprint')

        log.debug(f"Initialised operator with lulc_generator {os.environ.get('LULC_HOST')} and ohsome client")

    def info(self) -> Info:
        info = Info(name='Plugin Blueprint',
                    icon=Path('resources/icon.jpeg'),
                    version=Version(0, 0, 1),
                    concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
                    purpose='This Plugin serves no purpose besides being a blueprint for real plugins.',
                    methodology='This Plugin uses no methodology because it does nothing.',
                    sources=Path('resources/example.bib'))
        log.info(f'Return info {info.model_dump()}')

        return info

    def compute(self, resources: ComputationResources, params: ComputeInputBlueprint) -> List[Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        # The code is split into several functions from here.
        # Each one describes the functionality of a specific artifact type or utility.
        # Feel free to copy, adapt and delete them at will.

        # ## Artifact types ##
        # This function creates an example Markdown artifact
        markdown_artifact = OperatorBlueprint.markdown_artifact_creator(params, resources)

        # This function creates an example table artifact
        table_artifact = OperatorBlueprint.table_artifact_creator(params, resources)

        # This function creates an example image artifact
        image_artifact = OperatorBlueprint.image_artifact_creator(resources)

        # This function creates example chart artifacts
        chart_artifacts = OperatorBlueprint.chart_artifact_creator(params.float_blueprint, resources)

        # Further we have the geographic output types of raster and vector data.
        # We kill two birds with one stone and use the land-use and land-cover utility to demonstrate them.

        # ## Utilities ##

        # ### Ohsome ###
        # This function provides an example for the ohsome usage to create a vector artifact.
        vector_artifacts = self.vector_artifact_creator_and_ohsome_usage(params.get_geom(),
                                                                         params.date_blueprint,
                                                                         resources)

        # ### LULC ###
        # This function provides an example for the LULC utility usage to create a raster artifact.
        raster_artifact = self.raster_artifact_creator_and_lulc_utility_usage(params.get_geom(),
                                                                              params.date_blueprint,
                                                                              resources)
        artifacts = [markdown_artifact,
                     table_artifact,
                     image_artifact,
                     *chart_artifacts,
                     *vector_artifacts,
                     raster_artifact]
        log.debug(f'Returning {len(artifacts)} artifacts.')

        return artifacts

    @staticmethod
    def markdown_artifact_creator(params: ComputeInputBlueprint, resources: ComputationResources) -> Artifact:
        """This method creates a simple Markdown artifact.

        :param params: The input parameters.
        :param resources: The plugin computation resources.
        :return: A Markdown artifact.
        """
        log.debug('Creating dummy markdown artifact.')
        text = OperatorBlueprint.get_md_text(params)

        return create_markdown_artifact(text=text,
                                        name='A Text',
                                        tl_dr='A JSON-block of the input parameters',
                                        resources=resources,
                                        filename='markdown_blueprint')

    @staticmethod
    def table_artifact_creator(params: ComputeInputBlueprint, resources: ComputationResources) -> Artifact:
        """This method creates a simple table artifact.

        :param params: The input parameters.
        :param resources: The plugin computation resources
        :return: A table artifact.
        """
        table = OperatorBlueprint.create_table(params.string_blueprint)

        return create_table_artifact(data=table,
                                     title='Character Count',
                                     caption='The table lists the number of occurrences for each character in the '
                                             'input parameters.',
                                     description='A table with two columns.',
                                     resources=resources,
                                     filename='table_blueprint')

    @staticmethod
    def image_artifact_creator(resources: ComputationResources) -> Artifact:
        """This method creates a simple image artifact.

        :param resources: The plugin computation resources.
        :return: An image artifact.
        """
        log.debug('Creating dummy image artifact.')
        with Image.open('resources/cc0_image.jpg') as image:
            image_artifact = create_image_artifact(image=image,
                                                   title='Image',
                                                   caption='A nice image.',
                                                   description='The image is under CC0 license taken from [pexels]'
                                                               '(https://www.pexels.com/photo/person-holding-a-green-'
                                                               'plant-1072824/).',
                                                   resources=resources,
                                                   filename='image_blueprint')
        return image_artifact

    @staticmethod
    def chart_artifact_creator(incline: float,
                               resources: ComputationResources) -> Tuple[Artifact, Artifact, Artifact, Artifact]:
        """This method creates four simple chart artifacts.

        :param incline: Some linear incline of the data to make it more interactive.
        :param resources: The plugin computation resources.
        :return: Four graph artifacts.
        """
        scatter_chart_data, line_chart_data, bar_chart_data, pie_chart_data = OperatorBlueprint.chart_creator(incline)

        scatter_chart = create_chart_artifact(data=scatter_chart_data,
                                              title='The Points',
                                              caption='A simple scatter plot.',
                                              description='Beautiful points.',
                                              resources=resources,
                                              filename='scatter_chart_blueprint')

        line_chart = create_chart_artifact(data=line_chart_data,
                                           title='The Line',
                                           caption='A simple line of negative incline.',
                                           resources=resources,
                                           filename='line_chart_blueprint')

        bar_chart = create_chart_artifact(data=bar_chart_data,
                                          title='The Bars',
                                          caption='A simple bar chart.',
                                          resources=resources,
                                          filename='bar_chart_blueprint')

        pie_chart = create_chart_artifact(data=pie_chart_data,
                                          title='The Pie',
                                          caption='A simple pie.',
                                          resources=resources,
                                          filename='pie_chart_blueprint')

        return scatter_chart, line_chart, bar_chart, pie_chart

    def vector_artifact_creator_and_ohsome_usage(self,
                                                 aoi: shapely.MultiPolygon,
                                                 target_date: datetime.date,
                                                 resources: ComputationResources) \
            -> Tuple[Artifact, Artifact, Artifact]:
        """Ohsome example usage for vector artifact creation.

        :param aoi: The area of interest
        :param target_date: The date for which the OSM data will be requested
        :param resources: The plugin computation resources.
        :return: Three vector artifacts.
        """
        points, lines, polygons = self.vector_creator(aoi, target_date)

        point_artifact = create_geojson_artifact(features=points.geometry,
                                                 layer_name='Points',
                                                 caption='Schools in the area of interest including a dummy school in '
                                                         'the center.',
                                                 description='The schools are taken from OSM at the date given in the '
                                                             'input form.',
                                                 color=points.color.to_list(),
                                                 resources=resources,
                                                 filename='points_blueprint')

        line_artifact = create_geojson_artifact(features=lines.geometry,
                                                layer_name='Lines',
                                                caption='Buffers around schools in the area of interest including '
                                                        'a dummy school in the center.',
                                                description='The schools are taken from OSM at the date given in the '
                                                            'input form.',
                                                color=lines.color.to_list(),
                                                resources=resources,
                                                filename='lines_blueprint')

        polygon_artifact = create_geojson_artifact(features=polygons.geometry,
                                                   layer_name='Polygons',
                                                   caption='Schools in the area of interest including a dummy school '
                                                           'in the center, buffered by ca. 100m.',
                                                   description='The schools are taken from OSM at the date given in '
                                                               'the input form.',
                                                   color=polygons.color.to_list(),
                                                   resources=resources,
                                                   filename='polygons_blueprint')

        return point_artifact, line_artifact, polygon_artifact

    def raster_artifact_creator_and_lulc_utility_usage(self,
                                                       aoi: shapely.MultiPolygon,
                                                       target_date: datetime.date,
                                                       resources: ComputationResources) -> Artifact:
        """LULC Utility example usage for raster artifact creation.

        This is a very simplified example of usage for the LULC utility.
        It requests a user-defined area from the services for a fixed date and returns the result.

        :param aoi: The area of interest
        :param target_date: The date for which the classification will be requested
        :param resources: The plugin computation resources.
        :return: A raster artifact.
        """
        log.debug('Creating dummy raster artifact.')
        # Be aware that there are more parameters to the LULCWorkUnit which affect the configuration of the service.
        # These can be handed to the user for adaption via the input parameters.
        aoi = LULCWorkUnit(area_coords=aoi.bounds,
                           end_date=target_date.isoformat())

        with self.lulc_generator.compute_raster([aoi]) as lulc_classification:
            artifact = create_geotiff_artifact(data=lulc_classification.read(),
                                               crs=lulc_classification.crs,
                                               transformation=lulc_classification.transform,
                                               colormap=lulc_classification.colormap(1),
                                               layer_name='LULC Classification',
                                               caption='A land-use and land-cover classification of a user defined '
                                                       'area.',
                                               description='The classification is created using a deep learning model.',
                                               resources=resources,
                                               filename='raster_blueprint')

        return artifact

    @staticmethod
    def get_md_text(params: ComputeInputBlueprint) -> str:
        """Transform the input parameters to Markdown text with json blocks."""
        return f"""# Input Parameters

The Plugin Blueprint was run with the following parameters.
You can check if your input was received in the correct manner.
Be aware that if you did not specify a value, some of the optional parameters may use defaults.

```json
{params.model_dump_json(indent=4, exclude={'aoi_blueprint'})}
```

In addition the following area of interest was sent:

```json
{params.aoi_blueprint.model_dump_json(indent=4)}
```
"""

    @staticmethod
    def create_table(text: str) -> pd.DataFrame:
        """Counts the number of occurrences of each character in a string."""
        log.debug('Creating dummy table artifact.')
        data = [{'character': e, 'count': text.lower().count(e)} for e in set(text.lower())]
        table = DataFrame.from_records(data, index='character')
        table = table.sort_values(by=['count', 'character'],
                                  ascending=[False, True])
        return table

    @staticmethod
    def chart_creator(incline: float) -> Tuple[Chart2dData, Chart2dData, Chart2dData, Chart2dData]:
        """Creates a scatter plot, a line chart, a bar chart and a pie chart."""
        log.debug('Creating dummy chart artifacts.')

        x = list(range(0, 100, 10))
        y = [val * -abs(incline) for val in x]

        scatter_chart_data = Chart2dData(x=x,
                                         y=y,
                                         chart_type=ChartType.SCATTER)

        line_chart_data = Chart2dData(x=x,
                                      y=y,
                                      chart_type=ChartType.LINE)

        bar_chart_data = Chart2dData(x=[str(val) for val in x],
                                     y=y,
                                     chart_type=ChartType.BAR)

        y = [abs(int(val)) for val in y]
        pie_chart_data = Chart2dData(x=x,
                                     y=y,
                                     color=[Color('#a6cee3'),
                                            Color('#1f78b4'),
                                            Color('#b2df8a'),
                                            Color('#33a02c'),
                                            Color('#fb9a99'),
                                            Color('#e31a1c'),
                                            Color('#fdbf6f'),
                                            Color('#ff7f00'),
                                            Color('#cab2d6'),
                                            Color('#6a3d9a')],
                                     chart_type=ChartType.PIE)

        return scatter_chart_data, line_chart_data, bar_chart_data, pie_chart_data

    def vector_creator(self,
                       aoi: shapely.MultiPolygon,
                       target_date: datetime.date) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """ Schools from OSM.

        First schools are requested as points from OSM. Then these points, a buffer and the buffer outline are
        returned as point, line and polygon GeoDataFrame."""
        log.debug('Creating dummy vector artifact.')
        ohsome_response = self.ohsome.elements.centroid.post(bpolys=aoi,
                                                             time=target_date,
                                                             filter='amenity=school')
        elements = ohsome_response.as_dataframe()
        elements['color'] = Color('blue')

        # We add a default element in case the output is empty
        waldo = gpd.GeoDataFrame({'color': [Color('red')], 'geometry': [aoi.centroid]}, crs='EPSG:4326')

        points = gpd.GeoDataFrame(pd.concat([elements, waldo]))
        points = points.reset_index(drop=True)[['color', 'geometry']]

        polygons = points.to_crs('ESRI:54012')
        polygons.geometry = polygons.buffer(100,
                                            resolution=2,
                                            cap_style=3)
        polygons = polygons.to_crs(4326)

        lines = polygons.copy()
        lines.geometry = lines.boundary

        return points, lines, polygons
