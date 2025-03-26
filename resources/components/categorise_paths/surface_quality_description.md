Surface quality refers to how smooth the surface of a path is, which determines how safe and comfortable it is for walking. The assessment takes the perspective of people with limited mobility, considering the smoothness requirements of wheelchairs and wheeled walking frames.

The classification is based on the values of the OpenStreetMap `smoothness`, `surface` and `tracktype` tags (in the order they are evaluated). While the values of `smoothness` directly correspond to our surface quality, they are only sparsely mapped. We therefore also use the `surface` (surface material) and `tracktype` (surface firmness and maintenance status) to infer surface quality when `smoothness` tags are missing. While some surface materials are almost always too bumpy (e.g., cobblestones) or difficult to walk on (e.g., sand), for many others the surface quality depends on the path's maintenance state. This indicator assigns surface quality values to paths with only `surface` information assuming paths are well maintained, adding the prefix "Potentially" to indicate this uncertainty.

The following tables show the exact mapping of `smoothness`, `surface`, and `tracktype` tag values to surface quality values.



