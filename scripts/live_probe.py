"""First live run of Nova's own pipeline: run_session against a scratch dir.
Runbook Step 4. Requires nova[agent] + a working claude/Bedrock environment."""
import asyncio
import tempfile
from pathlib import Path

from nova.events.store import EventStore
from nova.index.db import connect
from nova.sessions.runner import collect, outcome, run_session


async def main():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "nova-home"
        con = connect(home / "index.db")  # connect() creates parents
        events = EventStore(home / "events")
        evs = await collect(run_session(
            con, events, Path(td), "Reply with exactly: PIPELINE_OK",
            max_turns=1,
        ))
        for ev in evs:
            print(ev.kind.value, "|", str(ev.payload)[:100])
        print("outcome:", outcome(evs))


asyncio.run(main())
