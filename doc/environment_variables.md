# Settings and Environment Variables

There are several `.env` files containing secrets and config options.

## `.env.base`
This file contains basic settings for the operation of the plugin.
They primarily control interactions with the infrastructure.
Some default values are provided in `.env.base_template`, you can copy them over to `.env.base`.

For a full list of options please see the [documentation in climatoology](https://gitlab.heigit.org/climate-action/climatoology/-/blob/main/docs/ca_base_settings.md?ref_type=heads):

## `.env`
This file contains miscellaneous settings, including options for the Naturalness Utility.

| Variable           | Description                                                                                                | Required | Default |
|--------------------|------------------------------------------------------------------------------------------------------------|----------|---------|
| `NATURALNESS_HOST` | Host for the [Naturalness Utility](https://gitlab.heigit.org/climate-action/utilities/naturalness-utility) | True     | -       |
| `NATURALNESS_PORT` | Port for the Naturalness Utility                                                                           | True     | -       |
| `NATURALNESS_PATH` | URL path to the Naturalness api endpoint                                                                   | True     | -       |

## `.env.ors`
This file contains options pertaining to the [openrouteservice](https://openrouteservice.org/)(ORS).
The options are defined in [mobility-tools](https://gitlab.heigit.org/climate-action/utilities/mobility-tools/-/blob/2.0.1/mobility_tools/settings.py?ref_type=tags).


| Variable                            | Description                                                           | Required                             | Default |
|-------------------------------------|-----------------------------------------------------------------------|--------------------------------------|---------|
| `ORS_BASE_URL`                      | URL of the ORS api if you do not want to use the public ORS api       | False                                | `None`  |
| `ORS_API_KEY`                       | API key for the ORS api                                               | only for public openrouteservice API | `None`  |
| `ORS_SNAPPING_RATE_LIMIT`           | Quota for snapping endpoint requests to the ORS                       | False                                | 100     |
| `ORS_SNAPPING_REQUEST_SIZE_LIMIT`   | Request size limit for snapping endpoint of ORS                       | False                                | 4999    |
| `ORS_DIRECTIONS_RATE_LIMIT`         | Quota for directions endpoint requests to the ORS                     | False                                | 40      |
| `ORS_DIRECTIONS_REQUEST_SIZE_LIMIT` | Request size limit for directions endpoint of ORS                     | False                                | 50      |
| `ORS_ISOCHRONE_MAX_REQUEST_NUMBER`  | Configurable maximum ORS isochrone requests per comfort artifact sent | False                                | 500     |
| `ORS_ISOCHRONE_MAX_BATCH_SIZE`      | Request size limit for isochrone endpoint of ORS                      | False                                | 5       |
| `ORS_COORDINATE_PRECISION`          | Coordinate precision used for ORS requests                            | False                                | .000001 |

## `.env.s3`
This file contains options pertaining to the s3 storage of high resolution elevation data.
The options are defined in [mobility-tools](https://gitlab.heigit.org/climate-action/utilities/mobility-tools/-/blob/2.0.1/mobility_tools/settings.py?ref_type=tags).
Some defaults are defined in `.env.s3_template` and can be copied over.

| Variable              | Description                                              | Required | Default |
|-----------------------|----------------------------------------------------------|----------|---------|
| `S3_ENDPOINT`         | Endpoint to s3 storage with pmtile elevation data        | True     | -       |
| `S3_ACCESS_KEY`       | Access key for s3 storage                                | True     | -       |
| `S3_SECRET_KEY`       | Secret key for s3 storage                                | True     | -       |
| `S3_SECURE`           | Whether to use a secure SSL connection to s3 storage     | False    | `True`  |
| `S3_BUCKET`           | S3 bucket with highres elevation data                    | True     | -       |
| `S3_DEM_VERSION`      | Version of the highres elevation data in s3              | True     | -       |
| `S3_DEFAULT_FILENAME` | Filename for the global fallback elevation pmtiles in s3 | True     | -       |

## `.env.feature`
Feature flags can be set in this file.
The possible feature flags are defined in the [settings](../walkability/core/settings.py).

| Variable              | Description                            | Required | Default |
|-----------------------|----------------------------------------|----------|---------|
| `FEATURE_FLAG_SHADE`  | Feature flag to enable shade indicator | False    | `False` |