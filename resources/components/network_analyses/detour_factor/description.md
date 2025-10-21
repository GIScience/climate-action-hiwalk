Detour factors measure how directly you can walk to surrounding locations.
The detour factor for a given cell is the average ratio between the walking distance and the straight-line (Euclidean) distance, i.e. “as the crow flies”, from the center of each cell to the center of adjacent cells.
Cells without walkable paths are assumed to have an infinite detour.

Cells are classified as follows:
- Medium Detour if it takes on average twice the straight-line distance to reach the neighbouring cells
- High Detour if it takes on average three times the straight-line distance to reach the neighbouring cells
- Unreachable if at least one neighbouring cell cannot be routed to or the cell does not contain paths

Cells with a detour factor below 2 are not displayed on the map, as they are considered to have good connectivity and are thus not problematic.