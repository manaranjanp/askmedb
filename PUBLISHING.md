# Publishing AskMeDB to PyPI

Once published, users can install with `pip install askmedb` or `uv add askmedb`.

## Prerequisites

1. **Create a PyPI account** at https://pypi.org/account/register/
2. **Create an API token** at https://pypi.org/manage/account/token/
   - Scope: "Entire account" for the first upload, then restrict to the `askmedb` project

## Option A: Using `build` + `twine`

### Install build tools

```bash
pip install build twine
```

### Build the package

```bash
python -m build
```

This creates `dist/askmedb-0.1.0.tar.gz` and `dist/askmedb-0.1.0-py3-none-any.whl`.

### Upload to TestPyPI first (optional but recommended)

```bash
twine upload --repository testpypi dist/*
```

Test the install:

```bash
pip install --index-url https://test.pypi.org/simple/ askmedb
```

### Upload to PyPI

```bash
twine upload dist/*
```

When prompted, use `__token__` as the username and your API token as the password.

### Verify

```bash
pip install askmedb
python -c "from askmedb import AskMeDBEngine; print('OK')"
```

## Option B: Using `uv`

```bash
uv build
uv publish
```

`uv publish` will prompt for your PyPI token. You can also set it via:

```bash
export UV_PUBLISH_TOKEN=pypi-...
uv publish
```

## After Publishing

Both `pip install askmedb` and `uv add askmedb` will work automatically — PyPI is the shared registry for both tools.

## Updating the Version

1. Update `version` in `pyproject.toml`
2. Rebuild: `python -m build` (or `uv build`)
3. Upload: `twine upload dist/*` (or `uv publish`)

## GitHub Repo Rename

After renaming the GitHub repo from `askdb` to `askmedb`:

1. Go to **Settings** > **General** > **Repository name** and change to `askmedb`
2. GitHub auto-redirects the old URL, but update any pinned links
3. Update the Colab notebook badge URL if needed
