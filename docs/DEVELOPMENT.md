# Development

Copy `.env.example` to `.env` and replace local-only placeholder passwords. Use `make setup`, `make up`, `make migrate`, and `make seed`. `make dev` is foreground Compose; `make test` and `make lint` run containerized checks. The UI runs at 5173 and API docs at 8000/docs.

Use Python 3.12+ and Node 22 if running outside containers. The local identity `local-demo-user` is explicitly not production authentication. Do not place cloud credentials in `.env` for the deterministic MVP.
