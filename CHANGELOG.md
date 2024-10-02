# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project mostly adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased](https://gitlab.heigit.org/climate-action/plugins/walkability/-/compare/demo...main?from_project_id=840&straight=false)

### Changed
- Updated the naming of walkability categories. ([#115](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/115))
- Combined walkability categories "Dedicated Exclusive" and "Dedicated Separated" into "Designated".([#122](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/122))
- Changed the way filtering is done. First, the full dataset is requested from OHSOME, and then the dataframe is filtered.
- Improve filtering for the walkability classes.
- Updated docker registry URL and dependencies.
- Move to approval tests.
- Climatology updated (to 3.1.15).
- Updated the yml file for Gitlab pipeline. (.gitlab-ci.yml)

### Added
- Restricted ohsome test time, so that the plugin fails fast in case of ohsome issues.
- Pavement quality indicator first draft added.
- Added first draft and inverse distance weighing for connectivity indicator.

### Fixed
- Defined service roads with bus=[designated, yes] as inaccessible. ([#121](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/121)])
- Roads without sidewalk included in shared_with_high_speed. ([#125](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/125))
- Railway platforms removed from inaccessible. ([#114](https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/114))
- Updated ohsome-py to assert that the required name attribute is available in the boundary request.
- Changed explicit filter to not ignore sidewalks if there is a separate sidewalk on one side
- Paths split into lines and polygons.
- Used better naming for aggregation files to prevent collision.

## [Demo](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases) - 2024-03-04

### Added
- Regional aggregation charts.
- Functionality to retrieve and display walkable paths.

## [Dummy](https://gitlab.heigit.org/climate-action/plugins/walkability/-/releases) - 2024-02-27

### Added
- Architecture of the Walkability plugin with sample output. Creates one walkability class with all paths in the area of interest colored blue.
