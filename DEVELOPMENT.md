# How to prepare a development environment

1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/):

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies & pre-commit hooks:

```shell
uv sync --only-group dev
uv run pre-commit install
```

3. (Optional) Activate the virtual environment:

```shell
source .venv/bin/activate
```

4. Run tests & mypy using tox:
```shell
uv run tox
```
