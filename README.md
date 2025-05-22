# <img src="doc/icon.png" width="5%"> Walkability

The Walkability plugin, created in cooperation with [PLANUM Fallast & Partner GmbH](https://planum.co.at).

## Development setup

To run your plugin locally requires the following setup:

1. Set up the [infrastructure](https://gitlab.heigit.org/climate-action/infrastructure) locally in `devel` mode
2. Copy your [.env.base_template](.env.base_template) to `.env.base` and [.env_template](.env_template) to `.env` and
   update them
3. Run `poetry run python plugin_showcase/plugin.py`

## Contributing

To contribute, install the dependencies

```shell
poetry install
```

and the pre-commit hooks:

```shell
poetry run pre-commit install
```

## Tests

To run all tests:

```shell
poetry run pytest
```

Some tests are [ApprovalTests](https://github.com/approvals/approvaltests.Python).
Approval tests capture the output (snapshot) of a piece of code and compare it
with a previously approved version of the output.

Once the output has been *approved* then as long as the output stays the same
the test will pass. A test fails if the *received* output is not identical to
the approved version. In that case, the difference of the received and the
approved output is reported to the tester. The representation of the report can
take many forms: The default is a print out of the difference to the console. You can also choose to use a diff-tool
instead:

```bash
# Meld
pytest \
    --approvaltests-add-reporter="meld"
# PyCharm
pytest \
    --approvaltests-add-reporter="pycharm-community" \
    --approvaltests-add-reporter-args="diff"
# Nvim
pytest \
    -s  \
    --approvaltests-add-reporter="nvim" \
    --approvaltests-add-reporter-args="-d"
```

## Docker (for admins and interested devs)

If the [infrastructure](https://gitlab.heigit.org/climate-action/infrastructure) is reachable you can
copy [.env.base_template](.env.base_template) to `.env.base` and then run

```shell
DOCKER_BUILDKIT=1 docker build --secret id=CI_JOB_TOKEN . --tag heigit/ca-walkability:devel
docker run --env-file .env.base --network=host heigit/ca-walkability:devel
```

Make sure your git access token is copied to the text-file named `CI_JOB_TOKEN` that is mounted to the container build
process as secret.

To deploy this plugin to the central docker repository run

```shell
DOCKER_BUILDKIT=1 docker build --secret id=CI_JOB_TOKEN . --tag heigit/ca-walkability:devel
docker image push heigit/ca-walkability:devel
```


To mimic the build behaviour of the CI you have to add `--build-arg CI_COMMIT_SHORT_SHA=$(git rev-parse --short HEAD)`
to the above command.