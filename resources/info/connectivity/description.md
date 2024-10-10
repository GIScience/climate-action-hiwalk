For each segment the connectivity is calculated as:

$\text{connectivity}= \frac{\text{#(Segments in AOI)}}{\text{∑(Weighting of reachable segments)}}$,

where the AOI is centred on the root segment with a radius corresponding to the maximum walking distance:

$\text{Maximum walking distance} = \text{Walking speed}*\text{Maximum trip time}$

and a destination segment in the AOI is counted as reachable if:

$\text{Actual walking distance} ≤ \text{Maximum walking distance}$

The weighting of the reachable segments is determined from the beeline distance to the root segment using a distance decay function chosen in the input. One can choose between:

No decay:
* $w(d)=1$

Polynomial decay ([Frank et al. 2010](https://bjsm.bmj.com/content/44/13/924)):
* $w(d)=$
  * $[335.9229 * d^5 - 1327.84 * d^4 + 1802.56 * d^3 - 935.68 * d^2 + 61.92 * d + 100.1072] / 100 $ if d ≤ 1.5
  * 0 if d > 1.5

(Default) A step function ([Xia et al. 2018](https://www.mdpi.com/2071-1050/10/11/3879/pdf?version=1540460686)):
* $w(d)= $
  * 1 if d < 0.4
  * 0.6 if d < 0.8
  * 0.25 if d < 1.2
  * 0.08 if d < 1.8
  * 0 if d ≥ 1.8

where $w$ is the weighting and $d$ the beeline distance in kilometers.