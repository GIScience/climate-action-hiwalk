# <img src="doc/icon.png" width="5%"> Walkability

The Walkability plugin, created in cooperation with [PLANUM Fallast & Partner GmbH](https://planum.co.at).

## Contributing

To contribute, install the dependencies

```shell
poetry install
```

and the pre-commit hooks:

```shell
poetry run pre-commit install
```


## Docker (for admins and interested devs)

If the [infrastructure]() is reachable you can copy [.env_template](.env_template) to `.env` and then run

```shell
DOCKER_BUILDKIT=1 docker build --secret id=CI_JOB_TOKEN . --tag heigit/ca-walkability:devel
docker run --env-file .env --network=host heigit/ca-walkability:devel
```

Make sure your git access token is copied to the text-file named `CI_JOB_TOKEN` that is mounted to the container build process as secret.

To deploy this plugin to the central docker repository run

```shell
DOCKER_BUILDKIT=1 docker build --secret id=CI_JOB_TOKEN . --tag heigit/ca-walkability:devel
docker image push heigit/ca-walkability:devel
```
