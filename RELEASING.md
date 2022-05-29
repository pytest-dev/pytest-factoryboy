# How to make a release

1. Bump the version:
```shell
poetry version <newversion>
```
2. Update the [CHANGES.rst](CHANGES.rst) file with the release notes and the new version.
3. Build and publish the package:
```shell
poetry publish --build
```
