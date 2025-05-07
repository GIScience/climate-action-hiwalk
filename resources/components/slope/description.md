Steep slopes make walking more strenuous and unsafe, especially for people with limited mobility.
This indicator estimates the slope of paths based on their elevation at the start and end point using
the [openelevationservice](https://github.com/GIScience/openelevationservice).
The results are currently based on a 90x90 m Shuttle Radar Topography Mission (SRTM) digital elevation model. Since this
spatial resolution is quite coarse for sub-city analyses, slopes may be underestimated in relatively flat areas.
Conversely, slope can be sharply overestimated for short road segments that begin and end in different grid cells of the
digital elevation model.

Paths are classified into three categories based on their estimated slope (%):
- 0 to 5%: “Suitable” for most, including older adults and wheelchair users.
- 5% to 8%: "Acceptable", but somewhat strenuous.
- More than 8%: "Inappropriate" for many and potentially unsafe.

This categorization and its rationale are thoroughly described in Alves et al. 2020 (doi:10.3390/su12187360) and based
on the recommendations of the Portuguese Institute for Mobility and Land Transports.
