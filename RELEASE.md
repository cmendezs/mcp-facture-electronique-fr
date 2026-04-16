# Release Process

This document describes how to release a new version of `mcp-facture-electronique-fr` to PyPI and the official MCP registry.

## Prerequisites (one-time setup)

### PyPI token

Generate a token at: https://pypi.org/manage/account/token/
- Scope: `Project: mcp-facture-electronique-fr`

Add it to `.env` at the root of this project:

```bash
echo "UV_PUBLISH_TOKEN=pypi-XXX" >> .env
```

`direnv` loads it automatically when you enter this directory — no need to set it globally.

### direnv

`direnv` auto-loads `.env` when you `cd` into the project. The `.envrc` file at the root is already configured.

Install and hook into your shell (one-time):

```bash
# Install
curl -sfL https://direnv.net/install.sh | bash

# Hook into zsh
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# Or for bash
echo 'eval "$(direnv hook bash)"' >> ~/.bash_profile
source ~/.bash_profile

# Allow the project
cd /Users/christophe/Documents/Claude/Projects/mcp-facture-electronique-fr
direnv allow
```

Verify the token is loaded:

```bash
echo $UV_PUBLISH_TOKEN  # should print your token
```

### MCP publisher CLI

The CLI is compiled from the official registry repo. It is stored in `/tmp` and is **lost on reboot** — recompile when needed:

```bash
# Prerequisites: Go 1.24.x (https://go.dev/dl/)
git clone https://github.com/modelcontextprotocol/registry.git /tmp/mcp-registry
cd /tmp/mcp-registry
make publisher
# Binary is at /tmp/mcp-registry/bin/mcp-publisher
```

Verify Go is installed:

```bash
go version  # must be 1.24.x or higher
```

---

## Release steps

### 1. Bump the version

Edit **both** files — replace `X.X.X` with the new version (e.g. `0.1.2` → `0.1.3`):

- `pyproject.toml` → `version = "X.X.X"`
- `server.json` → `"version": "X.X.X"` and `"version": "X.X.X"` (in `packages[]`)

### 2. Build and publish to PyPI

Make sure you are in the project directory (so `direnv` loads the token):

```bash
cd /Users/christophe/Documents/Claude/Projects/mcp-facture-electronique-fr
uv build && uv publish
```

### 3. Commit, tag and push

```bash
git add pyproject.toml server.json
git commit -m "chore: bump version to X.X.X"
git tag vX.X.X
git push origin main --tags
```

### 4. Publish to the MCP registry

Recompile the CLI if needed (after a reboot):

```bash
git clone https://github.com/modelcontextprotocol/registry.git /tmp/mcp-registry
cd /tmp/mcp-registry && make publisher
cd /Users/christophe/Documents/Claude/Projects/mcp-facture-electronique-fr
```

Then publish:

```bash
/tmp/mcp-registry/bin/mcp-publisher publish
```

On first use after a reboot, authenticate with GitHub first:

```bash
/tmp/mcp-registry/bin/mcp-publisher login github
/tmp/mcp-registry/bin/mcp-publisher publish
```

Expected output:
```
✓ Successfully published
✓ Server io.github.cmendezs/mcp-facture-electronique-fr version X.X.X
```

---

## Notes

- The MCP registry does **not** sync automatically with PyPI or GitHub — step 4 is required for every release.
- The `server.json` description field must be **≤ 100 characters**.
- GitHub Actions will automatically build and publish to PyPI on tag push (`.github/workflows/publish.yml`) — in that case, skip step 2.
- Each project should have its own PyPI token (scoped to that project) stored in its own `.env`.
