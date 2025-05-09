hiWalk is currently composed of two core indicators:
1. **Path category**: A categorisation of walkable paths based on which other users share the path with pedestrians
(such as bicycles and/or motorised traffic).

2. **Surface quality**: A grading of the paths' surface quality based on its reported smoothness or surface material. For transparency and interpretability, hiWalk separately displays each path's surface type and smoothness value.

In addition, hiWalk includes three optional indicators, which you can unselect to avoid slow computations:
1. **Detour factor**: A metric of how many times longer you need to walk to locations in your surroundings, compared to travelling in a straight line (aka "as the crow flies")

2. **Naturalness**: An index measuring how "natural" (i.e., how green and/or blue) are the immediate surroundings (10-m buffer) of a walkable path.

3. **Slope**: Slope of each walkable path (in %) calculated by comparing the elevation at each end of the path.

After computing hiWalk for an area of interest and selecting one of the indicator results, the 'Description' page
includes further details about the indicator's data and methodology.

**Important**: Except for the initial categorisation of walkable paths, the other indicators are only calculated for path categories deemed "potentially walkable". By default, this only applies to "Not walkable" paths, which are excluded from the calculation of the other indicators (i.e., Surface Quality, Naturalness, Slope, and Detour Factor). Before starting a new assessment, you can define which path categories are "Potentially walkable" and should thus be included in the rest of the analyses.

### Path categories

| Category Name                     | Description                                                           |
|-----------------------------------|-----------------------------------------------------------------------|
| Designated                        | Pedestrians have a designated path (e.g. roads with sidewalks)        |
| Shared with bikes                 | Path shared with cyclists, but no motorised traffic                   |
| Shared with slow cars             | Path shared with (or close to) slow motorised traffic (up to 10 km/h) |
| Shared with medium speed cars     | Path shared with motorised traffic (speed limit up to 30 km/h)        |
| Shared with fast cars             | Path shared with motorised traffic (speed limit up to 50 km/h)        |
| Shared with cars of unknown speed | Path shared with motorised traffic (speed limit unknown)              |
| Not walkable                      | Paths deemed too dangerous to walk on or with forbidden access        |
| Unknown                           | Insufficient information to classify (e.g. missing sidewalk tag)      |


### Data
The indicators are primarily based on the [OpenStreetMap (OSM)](https://www.openstreetmap.org/about) database.
OSM is a free and open geo-database with rich information about streets, paths,
and other important walkable infrastructure. OSM is created and maintained by volunteers. If the data for your area
of interest seem inaccurate and/or incomplete, you can help improve them by mapping your area in OSM using,
for example, the [StreetComplete](https://streetcomplete.app/) app (currently only available for Android).