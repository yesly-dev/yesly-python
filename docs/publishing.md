# Publishing to PyPI

The package is `yesly` (`pip install yesly`). Releases are published by
`.github/workflows/release.yml` when a `v*` tag is pushed. It uses PyPI trusted
publishing (OIDC from GitHub Actions), so no PyPI token is stored anywhere.

## One-time setup

1. **PyPI account.** Sign up at <https://pypi.org/account/register/> with a
   shared address and turn on two-factor authentication, which PyPI requires to
   publish.
2. **Pending trusted publisher.** This reserves the name before the first
   upload: on 2026-11-07, `yesly` was free. Go to *Your account* →
   *Publishing* → *Add a new pending publisher* → *GitHub*:
   - PyPI project name: `yesly`
   - Owner: `yesly-dev`
   - Repository name: `yesly-python`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. **GitHub environment.** In the repo, *Settings* → *Environments* → create
   `pypi`. Optionally add required reviewers.
4. **Optional dry run on TestPyPI.** Repeat step 2 on <https://test.pypi.org>.
   Then point a copy of the workflow at it with
   `repository-url: https://test.pypi.org/legacy/`.

The repo can stay private for PyPI. Making it public lets PyPI show the source
link and attestations.

## Each release

1. Bump `__version__` in `src/yesly/_version.py`. `pyproject.toml` reads it.
2. Merge to `main`.
3. Tag and push:

   ```bash
   git tag v0.2.0 && git push origin v0.2.0
   ```

The `build` job checks the tag against the version, runs the tests and builds
the wheel and sdist. The `publish` job uploads them. The first run turns the
pending publisher into the real `yesly` project. Check it at
<https://pypi.org/project/yesly/>.

## If something goes wrong

- A file name can never be uploaded twice, even after a delete. Fix forward
  with a new version.
- *Yank* a bad release on PyPI (project → *Releases* → *Options* → *Yank*).
  Pinned installs keep working and new installs skip it.
