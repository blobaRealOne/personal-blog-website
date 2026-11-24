# Personal Blog Website

Simple self-hosted blog website with admin panel.

Project idea based from [roadmap.sh](https://roadmap.sh/projects/personal-blog).

> [!WARNING]
> This probably should be obvious, but this project is not production-ready.

## Features

- View published articles
- CRUD operations through the admin panel
- HTTP Basic Authentication for admin access
- CSRF protection for POST request
- Comment feature
- Test coverage

## Tech Stack

- Python 3.15+
- Flask 3.1.3+
- Flask-WTF 1.3.0+

## Installation

Clone the repository:

```bash
git clone https://github.com/blobaRealOne/personal-blog-website.git
cd personal-blog-website
```

Then install dependencies:

### Using uv:

```bash
uv sync
```

This creates a virtual environment and installs dependencies using `uv.lock`.

### Using pip:

Make sure Python 3.15 or newer is installed.

Create and activate virtual environment.

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/MacOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install dependencies:

```bash
python -m pip install -e .
```

This reads `pyproject.toml` and installs its dependencies.

## Usage

**Using uv:**

```bash
uv run flask --app src.app run
```

**Using Python:**

```bash
python -m flask --app src.app run
```

Open http://localhost:5000 in your browser.
To access the admin panel, visit http://localhost:5000/admin
and enter your credentials.

By default, both the username and password are `admin`.

### Environment Variables

The application supports two environment variables for configuring admin credentials:

- `ADMIN_USER` - admin username. Defaults to `admin`.
- `ADMIN_PASSWORD` - admin password. Defaults to `admin`.
- `SECRET_KEY` - Flask secret key, used for session signing
and CSRF protection. Defaults to `secret_key`.

Setting these variables is optional, though you can override the defaults
by setting the environment variables before starting the application.

Here’s how to set them:

**Windows (PowerShell):**

```powershell
$env:ADMIN_USER = "<your_username>"
$env:ADMIN_PASSWORD = "<your_password>"
$env:SECRET_KEY = "<your_secret_key>"
```

**Linux/macOS:**

```bash
export ADMIN_USER="<your_username>"
export ADMIN_PASSWORD="<your_password>"
export SECRET_KEY="<your_secret_key>"
```

These variables apply only to the current terminal session.
