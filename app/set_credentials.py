"""Write config/credentials.json without a shell expanding `$` in the password.

Usage (stdin, two lines — email then password):

    printf '%s\\n%s\\n' 'you@example.com' 'my$ecureP@ss' | docker exec -i fbtv python -m app.set_credentials

Or encode the password as base64 (no `$` in the file at all):

    printf '%s' 'my$ecureP@ss' | base64 -w0; echo
    # then put FUBO_PASS_B64=<that> in credentials.env
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    config_dir = Path(os.environ.get("CONFIG_DIR", "./config")).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = [line.rstrip("\r\n") for line in sys.stdin.read().splitlines()]
    lines = [line for line in lines if line != ""]
    if len(lines) < 2:
        sys.stderr.write("Provide email on line 1 and password on line 2 (stdin).\n")
        sys.exit(2)
    user, password = lines[0], lines[1]
    path = config_dir / "credentials.json"
    path.write_text(
        json.dumps({"FUBO_USER": user, "FUBO_PASS": password}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"Wrote {path} user={user} pass_len={len(password)} has_dollar={'$' in password}\n")


if __name__ == "__main__":
    main()
