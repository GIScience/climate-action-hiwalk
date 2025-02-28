We define permeability as the average ratio between the distance in a straight line (i.e. Euclidean distance, aka "as the crow flies") and the actual walking distance through the path network from a given point to all other locations in an area of interest (AOI).

The AOI includes all road intersections within a given maximum distance which users can define based on their selected walking speed and maximum trip duration.

For each node in the path network, permeability is calculated as:

`Permeability = (∑(Euclidean distance / Walking distance)) / number of nearby nodes`

where the AOI is centred on a given node with a radius corresponding to the maximum walking distance:

`Maximum walking distance = Walking speed * Maximum trip time * 2`

and a destination node is considered "nearby" if:

`Euclidean distance ≤ Maximum walking distance`
