# Dependency feedstocks

Conda recipes for GOATS dependencies that are not available on conda-forge.
They exist to support `jdaviz` (see the dependency graph below); everything
else GOATS needs resolves from conda-forge or the Gemini astroconda channel.

| Feedstock | Why it is here |
| --- | --- |
| `jdaviz-feedstock` | Not packaged on conda-forge. |
| `stdatamodels-feedstock` | Not packaged on conda-forge; required by jdaviz. |
| `ipypopout-feedstock` | Not packaged on conda-forge; required by jdaviz. |
| `ipysplitpanes-feedstock` | Not packaged on conda-forge; required by jdaviz. |
| `ipygoldenlayout-feedstock` | Not packaged on conda-forge; required by jdaviz. |
| `ipyvuedraggable-feedstock` | conda-forge only has 1.0.0; jdaviz needs >=1.1.0. |

All recipes are `noarch: python` (the widget sdists ship prebuilt JS, so no
node/npm is needed at build time).

## Publishing

Packages are built and published with the
[`build_and_publish_deps.yaml`](../.github/workflows/build_and_publish_deps.yaml)
workflow (manual dispatch). It builds the selected feedstock and opens a PR
adding the package to one of the GitHub Pages channels:

- **Test:** `https://gemini-hlsw.github.io/goats-infra/conda-test` (default)
- **Production:** `https://gemini-hlsw.github.io/goats-infra/conda`

Publish to `conda-test` first, verify the install, then re-run the workflow
targeting `conda` to promote.

### Order matters

`jdaviz`'s test phase resolves its run dependencies, so the other five
packages must already be published (at least to `conda-test`) before building
`jdaviz`:

1. `ipysplitpanes`, `ipygoldenlayout`, `ipyvuedraggable`, `ipypopout`,
   `stdatamodels` — any order.
2. `jdaviz`.

### Verifying an install from the test channel

```bash
conda create -n jdaviz-test \
  -c https://gemini-hlsw.github.io/goats-infra/conda-test \
  -c conda-forge \
  --override-channels \
  jdaviz
```

## Updating a recipe

Bump `version` and `sha256` in the recipe's `meta.yaml` (sdist checksums are
on PyPI under the release's "Download files"), reset `number: 0` if the
version changed, and re-run the workflow.
