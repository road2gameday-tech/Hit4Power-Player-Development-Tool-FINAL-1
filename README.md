
# Hit4Power Player Development Tool

FastAPI + Jinja + SQLite app for instructors and players.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SESSION_SECRET=devsecret
export INSTRUCTOR_CODE=MASTER123
uvicorn app.main:app --reload
```

## On Render
- Add a 1GB Disk mounted at `/data`
- Set env vars in `render.yaml` (or in dashboard)

## Notes
- Player avatars and drill videos stored in `/data/avatars` and `/data/drills`.
- SMS via Twilio if env vars are set.
