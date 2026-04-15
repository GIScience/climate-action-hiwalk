Detour factors measure how directly you can walk to surrounding locations.
The detour factor for a given cell is the average ratio between the walking distance and the straight-line (Euclidean) distance, i.e. “as the crow flies”, from the center of each cell to its corners.
Cells without walkable paths around the center of the cell are dropped.

Cells are classified as follows:
- Medium Detour if it takes on average twice the straight-line distance to reach the corners
- High Detour if it takes on average three times the straight-line distance to reach the corners
- Unreachable if at least one corner cannot be reached

Cells with a detour factor below 2 are not displayed on the map, as they are considered to have good permeability and are thus not problematic.