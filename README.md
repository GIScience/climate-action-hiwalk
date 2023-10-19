# Plugin Blueprint

This repository is a blueprint for operator creators. Operators are science2production facilitators that will make it easy for you to bring your ideas and research results to the Climate Action (CA) platform. Operators are the main workers inside plugins. You will create a plugin but all you need to do is code the operator functionality, the plugin wrapper is already set to go. The terms Operator and Plugin are therefore mostly synonymous for you. For more information on the architecture, please contact the [CA team](https://heigit.org/).

Please follow the subsequent steps to bring your plugin to life.

## Preparation

A new plugin should be thoroughly discussed with the CA team. But don't be hesitant, they are very welcoming to new ideas :-) !

### Git

The CA team will fork **this** repository for you and you will get full access to the fork. You can then `git clone` the fork and work on it as in any other git project.

Create a new branch by running `git checkout -b <my_new_plugin_name>`.
After you have finished your implementation, you can create a merge request to the `main` branch that can be reviewed by the CA team.
Yet we highly encourage you to create smaller intermediate MRs for review.

### Python Environment

We use [mamba](https://mamba.readthedocs.io/en/latest/) (i.e. conda) as an environment management system.
Make sure you have it installed.
Apart from some base dependencies, there is only one fixed dependency for you, which is the [climatoology](https://gitlab.gistools.geog.uni-heidelberg.de/climate-action/climatoology) package that holds all the infrastructure functionality.

The CA team will provide you with an access token. Head over to the [environment.yaml](environment.yaml) and replace 
 
 - the environment name `ca-plugin-blueprint` with your plugin name. While we are at it, please also replace all occurences of that name in the [Dockerfile](Dockerfile).
 - put the provided git token in a file called `GIT_PROJECT_TOKEN`. Then run `export GIT_PROJECT_TOKEN=$(cat GIT_PROJECT_TOKEN)` to set the token as en environment variable

Run `mamba env create -f environment.yaml`. You are now ready to code within your mamba environment.

## Start Coding

We have seperated the code into multiple files by their functionality.
Three files are relevant for you:

1. The [operator.py](plugin/operator.py) that defines your operator logic,
2. the [input.py](plugin/input.py) that defines the user inputs required to run your plugin and
3. [test_plugin.py](test/test_plugin.py) where you define the unit tests for your plugin.

We will go through these files step by step.

### Tests in [test_plugin.py](test/test_plugin.py)

We highly encourage [test driven development](https://en.wikipedia.org/wiki/Test-driven_development).
In fact, we require two predefined tests to successfully run on your plugin.

 - The first test confirms that your plugin announcement is working as expected (`test_plugin_info_request`).
 - The second test ensures that your computation runs as expected in a test environment (`test_plugin_compute_request`).

These tests ensure that the development contract is met.

Therefore, before you start coding, please take some time to sketch the outline of your plugin.
You will need a clear _definition and description_ of your plugin as well as an idea of the required _input_ and the produced _output_.
You can of course adapt this later, but you should have a rough idea from the start.

Ensure all tests are passing on the unmodified repository.
Then open [test/test_plugin.py](test/test_plugin.py).
Adapt the content of the three `pytest.fixture` functions to meet your expectations:

 1. The `expected_info_output` fixture is quite easy to write:
simply declare an `Info` element.
Have a look at the classes source code to see all required attributes.
Make sure you add the icon and bibliography files to your repository.
The list of concerns is limited on purpose to have a curated set of keywords.
If you feel that your plugin would benefit from an extension of that list, feel free to contact the CA team or create a MR in the [climatoology](https://gitlab.gistools.geog.uni-heidelberg.de/climate-action/climatoology) repository.

 2. For now, you can leave the `expected_compute_input` as is.
It is better to update it, once you have made the first changes to the actual working code later.

 3. The `expected_compute_output` will probably grow over time.
But you should define a first output result you would like to create through your plugin.
Define it in the test and add the required file to the repository. 

That's it, the tests should fail, and you can start coding towards making them succeed.

Unfortunately, if you use external services, they need to be mocked.
The CA team can help you implement [mocks](https://docs.python.org/3/library/unittest.mock.html).
But let's create some code first.

### Names

We have to replace names at multiple level.
Let's start with refactoring the name of the `BlueprintComputeInput` and the `BlueprintOperator` classes in [plugin/plugin.py](plugin/plugin.py).
Replace these classnames with reasonable names related to your idea.

### Operator in [operator.py](plugin/operator.py)

#### Info Function

Now lets make the tests succeed.
For the info function this is very simple.
Just copy the test artifact declaration over to the plugin file.
Done.

#### Compute Function

Now comes the main coding part.
This function is where you can explode your genius and create ohsome results.
You are free to create additional classes or methods as needed or write a single script just as you would in jupyter.

You will probably also use external services like [ohsome-py](https://github.com/GIScience/ohsome-py).
In addition, you can use the provided utilities of the CA team.
A list of utilities can be found in the [climatoology](https://gitlab.gistools.geog.uni-heidelberg.de/climate-action/climatoology) repository, but we also provide examples for their usage in this repository.

The only requirement is to return a (potentially empty) list of Artifacts i.e. results.
Note that artifacts have a `file_path` attribute which takes a path to a file.
You therefore have to save all your (potential) results on disk and then pass that filename to the Artifact.
The plugin will then read the file and send it to the file store, but you don't have to worry about that.
Yet, your file should be written under a specific path in the system. The input parameter `resources` provides this path via the `resources.computation_dir` attribute.
Write all your output to that directory.

### Input parameters in [input.py](plugin/input.py)

Keep in mind to update the input parameter class and the tests while you are coding away.

## Finalisation

If you are satisfied with the results and the tests pass, you have succeeded!
Please create a merge request to `main` and ask the CA team for a review.

Unfortunately, seeing your plugin in production takes a bit more setup.
You will have to set up the [infrastructure](https://gitlab.gistools.geog.uni-heidelberg.de/climate-action/infrastructure) and set a range of environment variables.
But don't worry. Its documentation is just as extensive as this one.

After your plugin is ready for production, the CA team will create a Docker image and deploy your code to the infrastructure.

## Docker (for devs)

To deploy this plugin run

```shell
DOCKER_BUILDKIT=1 docker build --secret id=GIT_PROJECT_TOKEN . --tag heigit/{plugin-name}:devel
docker image push heigit/{plugin-name}:devel
```

If the infrastructure is reachable you can copy [.env_template](.env_template) to `.env` and then run 

```shell
docker run --env-file .env --network=host heigit/{plugin-name}:devel
```

Don't forget to add the plugin to the [infrastructure](https://gitlab.gistools.geog.uni-heidelberg.de/climate-action/infrastructure) and deploy it.
