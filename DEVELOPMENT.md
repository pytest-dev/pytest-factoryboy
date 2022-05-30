# How to prepare a development environment

1. [Install poetry](https://python-poetry.org/docs/#installation):

```shell
# MacOS / Linux
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -

# Windows
(Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py -UseBasicParsing).Content | python -
```

2. Install dependencies & pre-commit hooks:

```shell
poetry install

pre-commit install
```

3. (Optional) Activate the poetry virtual environment:

```shell
poetry shell
```

4. Run tests & mypy using tox:
```shell
tox
```
