hiWalk is currently composed of two core indicators:
1. **Path category**: A categorisation of walkable paths based on which other users share the path with pedestrians
(such as bicycles and/or motorised traffic).

2. **Surface quality**: A grading of the paths' surface quality based on its reported smoothness or surface material. For transparency and interpretability, hiWalk separately displays each path's surface type and smoothness value.

In addition, hiWalk includes three optional indicators, which you can unselect to avoid slow computations:
1. **Detour factor**: A metric of how many times longer you need to walk to locations in your surroundings, compared to travelling in a straight line (aka "as the crow flies")

2. **Greenness**: An metric how "green" (i.e., median NDVI) are the immediate surroundings (15-m buffer) of a walkable path.

3. **Slope**: Slope of each walkable path (in %) calculated by comparing the elevation at each end of the path.

After computing hiWalk for an area of interest and selecting one of the indicator results, the 'Description' page
includes further details about the indicator's data and methodology.

### Data
The indicators are primarily based on the [OpenStreetMap (OSM)](https://www.openstreetmap.org/about) database.
OSM is a free and open geo-database with rich information about streets, paths,
and other important walkable infrastructure. OSM is created and maintained by volunteers. If the data for your area
of interest seem inaccurate and/or incomplete, you can help improve them by mapping your area in OSM using,
for example, the [StreetComplete](https://streetcomplete.app/) app (currently only available for Android).