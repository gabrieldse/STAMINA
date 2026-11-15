# Contributing to STAMINA

Start with [README.md](README.md) to install dependencies, prepare NASA data,
and start the explorer. `main` contains the combined explorer, scientific API,
temperature maps, mission walkthrough, and standalone illumination tools.

For navigation, see [architecture](docs/architecture.md) and
[illumination tools](Filters/README.md). The original static prototype is under
`legacy/website/`; the active application is `frontend/` plus `backend/`.

## Make and check a change

Pull the latest `main`, create a focused working branch, and describe the user
behavior your change adds or fixes. Before proposing a merge, run:

```bash
python -m unittest discover -s tests
python -m unittest discover -s Filters/tests
npm --prefix frontend test
npm --prefix frontend run build
```

Install `requirements-dev.txt` first. API tests need the scientific data from
`python scripts/manage.py prepare-data`; some global-terrain tests contact NASA.
The standalone illumination tests use synthetic terrain and mocked downloads.

Document changes to scientific assumptions, coordinate conventions, units, or
sampling in the relevant guide. Include the commands you ran and their results
in the pull request. Merge completed work into `main` and remove merged working
branches so users always have one clear starting point.

Keep generated maps, terrain downloads, result images, bytecode, virtual
environments, dependency folders, credentials, and logs out of Git. The ignored
data must still be prepared when running the project from a fresh clone.
