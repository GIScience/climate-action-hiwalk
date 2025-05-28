# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project mostly adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased](https://gitlab.heigit.org/climate-action/plugins/walkability/-/compare/2.1.0...main)

## [2.1.0](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/2.1.0) - 2025-05-28

### Added

- A new detour indicator mapping the average ratio of the walking distance to the euclidian distance for cells in a hexgrid based on the ors directions and snapping endpoints ([#175](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/175), [#180](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/180))

### Changed

- "Not Walkable" paths are now split into two categories: "No access" and "Shared with cars above 50 km/h" ([#204](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/204))
- Updated legend labels for path categories shared with cars to include speed limit instead of category label
- Renamed input field to select optional indicators, making computation parameters report more understandable ([#224](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/224))
- The Naturalness indicator now includes only NDVI and was thus renamed "Greenness".
- Private paths and other streets with restricted access are now hidden from display to avoid cluttering the maps and distracting from problems in the public street network ([#222](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/222))

- Docker builds now take the commit hash as an argument to avoid version collisions on staging ([#226](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/226))
- CI pipeline now includes test-coverage checks ([#225](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/225))
- Updated ruff and pre-commit configs for more checks ([#181](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/181))
- Removed unused geometry and path rating helper functions

### Fixed
- Fix invalid path geometries ([#223](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/223))

## [2.0.1](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/2.0.1) - 2025-05-14

### Changed

- New simplified icon
- Shorten description of the assessment tool

## [2.0.0](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases/2.0.0) - 2025-05-13

### Changed

- Surface quality, surface type, smoothness, and naturalness now include polygon paths ([#203](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/203))
- Surface quality categories "excellent" and "good" were merged into a single category "
  good" ([138](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/138))
- Surface quality categories based on surface type now assume good road maintenance
  state ([138](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/138))
- Paths, where it is unclear if the user has to walk on the street, are now classified as '
  Unknown' ([144](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/144)). Before it was assumed, no
  sidewalk would be available.
- Summary charts of the sub-areas of the AOI are now horizontal stacked bar charts ([#209](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/209))
- Naturalness legend is now simpler and more concise ([#215](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/215))

- Remove default colormap from generate_colors ([#190](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/190))
- Update climatoology to 6.3.1: use `create_plotly_chart_artifact` and include `demo_input_parameters` in info

### Fixed

- Polished description of indicators:
  - naturalness ([#195](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/195))
  - surface quality ([#196](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/196))
  - walkable categories ([#197](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/197))
  - slope ([#200](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/200))
- Clean subregion names in areal summaries to deal with special characters ([#208](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/208))

- Filter ohsome boundaries to polygon geometries (in `summarise_by_area`), in case other geometry types make it through
  the ohsome API
- Fixed bug that threw error when calculating walkability for areas without polygon paths ([#87](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/87))

### Added

- New naturalness indicator, quantifying greenness (NDVI) and blueness (presence of water bodies) in a
  paths' immediate surroundings ([#21](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/21))
- New slope indicator depicting the slope in % of OSM ways based on openelevationservice (
  90x90m) ([#42](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/42))
- New smoothness and a new surface type indicator (components of the surface quality indicator) ([#172](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/172))
- Possibility for users to select which optional indicators to compute (slope and naturalness)

### Removed

- Node-based connectivity indicator in favor of a new hexgrid detour indicator to be included in next minor release ([#178](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/178))

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