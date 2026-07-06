"""FastAPI localhost backend (SPEC §7).

127.0.0.1 only, per-launch bearer token, strict CORS. Pure HTTP/WS surface —
the React frontend is a view over this API; no other IPC. Pydantic models
here are the OpenAPI source for generated TS types.
"""
