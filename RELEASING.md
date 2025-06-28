# How to make a release

1. Bump the version:
```shell
poetry version <newversion>
```
2. Update the [CHANGES.rst](CHANGES.rst) file with the release notes and the new version.
3. Commit the changes:
```shell
git add pyproject.toml CHANGES.rst
git commit -m "Bump version to <newversion>"
```
4. Create and push a tag:
```shell
git tag <newversion>
git push origin <newversion>
```

The GitHub Actions workflow will automatically build and publish the package to PyPI when a tag is pushed.
