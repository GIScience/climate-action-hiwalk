# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project mostly adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased](https://gitlab.heigit.org/climate-action/plugins/walkability/-/compare/1.1.0...main)

### Changed

- Merge PavementQuality categories "excellent" and "good" into "
  good" ([138](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/138))
- Modify "potential" pavement quality categorization based on surface tags to reflect good road maintenance
  state ([138](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/138))
- Paths, where it is unclear if the user has to walk on the street, are now classified as '
  Unknown' ([144](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/144)). Before it was assumed, no
  sidewalk would be available.
- Remove default colormap from generate_colors ([#190](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/190))
- Update climatoology to 6.2.0: use `create_plotly_chart_artifact` and include `demo_input_parameters` in info

### Fixed

- Filter ohsome boundaries to polygon geometries (in `summarise_by_area`), in case other geometry types make it through
  the ohsome API
- Fixed bug that threw error when calculating walkability for areas without polygon paths ([#87](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/87))
- Fixed typos in naturallness description ([#195](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/195))

### Added

- A new greenness indicator, mapping the NDVI score of walking
  paths ([#21](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/21))
- A new slope indicator depicting the slope in % of OSM ways based on openelevationservice (
  90x90m) ([#42](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/42))
- A new detour indicator mapping the average ratio of the walking distance to the euclidian distance for cells in a
  hexgrid
  ([#175](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/175))
- A new smoothness and a new surface type indicator (components of the surface quality indicator) ([#172](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/172))
- The option for users to select which optional indicators to compute (slope, naturalness, and detour factors)

### Removed

- The old node based connectivity indicator in favor of future proper accessibility indicators and the new hexgrid
  detour indicator ([#178](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/178))

## [1.1.0](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/1.1.0) - 2024-12-06

### Changed

- Connectivity is now a primary result of the plugin, on equal standing with the other indicators
- Changed colour scheme for connectivity result to `coolwarm`

- Added backend code for relations request
- Updated dependencies for climatoology (5.1.0 -> 6.0.2)

### Fixed

- Now connectivity indicator keeps "unwalkable" paths and assigns them connectivity of 0
- Connectivity legend inverted so that high connectivity values are on top

### Added

- Added edge cases like fords, designated lock gates, etc.

## [1.0.0](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/1.0.0) - 2024-10-14

### Changed

- Updated the naming of walkability
  categories ([#122](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/122)):
    - "Designated exclusive", "Dedicated Separated" and "Dedicated shared with bikes" categories combined and renamed "
      Designated"
    - Shared with motorized traffic categories now show speed limit range inside brackets
    - Inaccessible category renamed to "Not walkable"
    - Missing data category renamed to "Unknown"
- Used more color-blind friendly colormaps, switched to "equidistant" colormap

- Changed the way filtering is done. First, the full dataset is requested from OHSOME, and then the dataframe is
  filtered.
- Updated docker registry URL and dependencies.
- Climatoology updated (to 5.1.0).

### Added

- Pavement quality indicator first draft added.
- Added first draft and inverse distance weighing for connectivity indicator.

- Restricted ohsome test time, so that the plugin fails fast in case of ohsome issues.

### Fixed

- Defined service roads with bus=[designated, yes] as
  inaccessible. ([#121](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/121))
- Roads without sidewalk included in
  shared_with_high_speed. ([#125](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/125))
- Railway platforms removed from
  inaccessible. ([#114](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/114))
- Changed explicit filter to not ignore sidewalks if there is a separate sidewalk on one side

- Paths split into lines and polygons.
- Used better naming for aggregation files to prevent collision.
- Updated ohsome-py to assert that the required name attribute is available in the boundary request.

## [Demo](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/demo) - 2024-03-04

### Added

- Regional aggregation charts.
- Functionality to retrieve and display walkable paths.

## [Dummy](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases) - 2024-02-27

### Added

- Architecture of the Walkability plugin with sample output. Creates one walkability class with all paths in the area of
  interest colored blue.
