<p align="center">
  <img src="static/img/favicon.svg" alt="GlichFlow Logo" width="96" height="96" />
</p>

# GlichFlow

Simple and fast project/task management for your team.

- Live: [glichflow.glitchidea.com](http://glichflow.glitchidea.com/)
- Documentation: [glichflow.glitchidea.com/docs.html](http://glichflow.glitchidea.com/docs.html)
- Source: [github.com/glitchidea/GlichFlow](https://github.com/glitchidea/GlichFlow)

## What’s Included

- Projects and Tasks (assignment, status, files)
- Teams and Permissions
- Messaging and Notifications
- Calendar views
- Reports, GitHub integration, AI assistant

## Quick Start

```bash
git clone https://github.com/glitchidea/GlichFlow.git
cd glichflow
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# http://127.0.0.1:8000
```

For production and advanced setups, see the documentation.

## Roadmap
- English UI support via i18n (Django internationalization) — coming soon.

## License

AGPL-3.0 — see `LICENSE` for details.
