<h1 align="center">GitLab Dummy Data Seeder</h1>

<p align="center">
  <a href="#prerequisites">Prerequisites</a> |
  <a href="#installation">Installation</a> |
  <a href="#running">Running</a> |
  <a href="#customization-settingstoml">Customization</a> |
  <a href="#repository-structure">Repository Structure</a> |
  <a href="#license">License</a>
</p>

A customizable dummy data seeder for a GitLab instance for testing and development purposes.

### Prerequisites

- Python 3.11 or newer
- A GitLab access token with the `api` scope. `sudo` is recommended, and creating users require an admin token.

### Installation

```bash
git clone https://github.com/zsoltfrks/gitlab-dummy-data-seeder.git
cd gitlab-dummy-data-seeder
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

### Running

Copy the examples:

```bash
cp settings.example.toml settings.toml
cp .env.example .env
```

Put your GitLab URL and access token into `.env`:

```dotenv
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-...
```

Check the settings and the instance:

```bash
glseed validate
```

#### Tests

```bash
pytest
```

### Customization `settings.toml`

| Setting                  | Default  | Description                                                                                         |
| ------------------------ | -------- | --------------------------------------------------------------------------------------------------- |
| `seed`                   | `0`      | Seed for the random generators. The same seed and settings produce the same data.                   |
| `prefix`                 | `"seed"` | Prepended to the names of everything the seeder creates. 1–32 lowercase letters, digits or hyphens. |
| `gitlab.timeout_seconds` | `60`     | Seconds to wait for each API response.                                                              |
| `gitlab.verify_ssl`      | `true`   | Set to `false` only for test instances with self-signed certificates.                               |

### Repository Structure

```
├─ src/
│  ├─ cli.py                # `glseed` commands
│  ├─ settings.py           # settings.toml schema and .env connection
│  ├─ client.py             # python-gitlab client
│  └─ preflight.py          # readiness checks run by `glseed validate`
├─ tests/                   # pytest suite
├─ settings.example.toml    # copy to settings.toml
├─ .env.example             # copy to .env
└─ pyproject.toml           # packaging, dependencies and tool settings
```

### License

<hr>
<p align="center">
  <sub>
    <b>Keywords:</b> dummy data, dummy data seeder, gitlab, gitlab data seeder, python, test data generator, fake data generator, 
    sample data, test data seeding, gitlab automation, repository seeder, mock data, synthetic data, development tools, 
    automated testing, database seeder, gitlab synthetic data generator, automation, dummy, data, requests, api, testing purposes
  </sub>
</p>
