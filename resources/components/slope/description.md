Steep slopes or large amounts of moderate slopes reduce the accessibility of an area for some pedestrians and wheelchair
users.
This indicator estimates the slope of OSM paths based on the elevation at the start and end point using
the [openelevationservice](https://github.com/GIScience/openelevationservice).
The results are based on a 90x90m Shuttle Radar Topography Mission (SRTM) digital elevation model. Such spatial
resolution is rather coarse for sub-city analyses. As a result, slopes may be generally underestimated in relatively
flat areas. And, conversely, slope can be sharply overestimated for short road segments that begin and end in different grid cells.

Paths are colored based on Alves et al. (2020) slope bins:
- 0 to 5%: "Suitable slope" at which the elderly and people with limited mobility are not expected to overly exert themselves.
- 5% to 8%: "Acceptable slope", people with limited mobility might experience some physical exertion.
- More than 8%: "Inappropriate", physical exertion and safety risks increase.
