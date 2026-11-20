# Copyright © 2026 EuKreate, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The Action's checks: the network's checks of agent.json with a CI token, and, given the server's address,
whether agent.json still matches what the server and eukollab.json give. It writes nothing but its report. ekl runs
in the agent's folder, and reads the server's addresses from the EKL_UPSTREAM_* variables agent.json names: an MCP
server's, an HTTPS API's OpenAPI document (and the API's own address when it is elsewhere) or an A2A agent's."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Each input and the variable ekl reads it from. api goes with openapi: alone it names no server.
SERVERS = {
    "MCP": "EKL_UPSTREAM_MCP_URL",
    "OPENAPI": "EKL_UPSTREAM_OPENAPI_URL",
    "API": "EKL_UPSTREAM_API_URL",
    "A2A": "EKL_UPSTREAM_A2A_URL",
}


def servers() -> dict[str, str]:
    """The EKL_UPSTREAM_* variables for the server addresses the workflow gave."""
    return {variable: os.environ[name] for name, variable in SERVERS.items() if os.environ.get(name, "").strip()}


def run(
    *args: str, folder: Path | None = None, given: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **given} if given else None
    return subprocess.run(["ekl", *args], capture_output=True, text=True, check=False, cwd=folder, env=env)


def answered(checked: subprocess.CompletedProcess[str]) -> dict[str, Any] | None:
    """The answer `ekl --json check` gave, or None when it gave none. ekl exits 1 when the checks find errors, so the
    exit code alone can't tell a check that found problems from one that could not run: only a missing answer can."""
    try:
        answer = json.loads(checked.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(answer, dict):
        return None
    problems = answer.get("problems")
    if not isinstance(problems, list) or not all(isinstance(p, dict) for p in problems):
        return None
    return dict(answer)


def planned_problems(answer: dict[str, Any]) -> list[str]:
    """Each service agent.json plans to use that is no longer listed or changed since the plan was written."""
    uses = answer.get("uses")
    return [
        f"- error: planned service `{u.get('service')}` ({u.get('need') or '-'}): {u['problem']}"
        for u in (uses if isinstance(uses, list) else [])
        if isinstance(u, dict) and u.get("problem")
    ]


def diagnostics(done: subprocess.CompletedProcess[str]) -> str:
    """What the command said, for the report: its exit code and output, cut to a readable length."""
    said = (done.stderr.strip() + "\n" + done.stdout.strip()).strip() or "no output"
    return f"exit code {done.returncode}\n{said[:2000]}"


def main() -> int:
    file, platform, given = os.environ["FILE"], os.environ["PLATFORM"], servers()
    server = bool({"EKL_UPSTREAM_MCP_URL", "EKL_UPSTREAM_OPENAPI_URL", "EKL_UPSTREAM_A2A_URL"} & given.keys())
    # ekl checks the agent.json in the folder it runs in.
    folder = Path(file).parent
    lines = [f"### EuKollab check of `{file}`", ""]
    if Path(file).name != "agent.json":
        lines.append(f"**Nothing was checked:** ekl checks a file named `agent.json`, not `{Path(file).name}`.")
        print(f"::error title=EuKollab check-agent::{file} is not named agent.json.")
        return report(lines, failed=True)
    failed = False
    if os.environ.get("EKL_TOKEN"):
        login = run("login", "--platform", platform)
        if login.returncode != 0:
            lines += ["**Could not sign in with `EKL_TOKEN`:**", "", f"```\n{login.stderr.strip()}\n```"]
            failed = True
        else:
            checked = run("--json", "check", folder=folder, given=given)
            answer = answered(checked)
            if answer is None:
                # No answer, or one without its problems list, is a failure, never a pass.
                failed = True
                lines += ["**The network's checks could not run:**", "", f"```\n{diagnostics(checked)}\n```"]
            else:
                problems, planned = answer["problems"], planned_problems(answer)
                # ekl's own exit code also counts agent.json out of step with the server, which sync reports below.
                found = bool([p for p in problems if p.get("level") == "error"] or planned or checked.returncode)
                failed |= found
                lines.append("**The network's checks:** " + ("problems found" if found else "passed"))
                lines += [f"- {p.get('level')}: `{p.get('field') or '-'}` {p.get('message', '')}" for p in problems]
                lines += planned
    else:
        # GitHub gives no secrets to a pull request from a fork.
        lines.append("**The network's checks were skipped:** no `EKL_TOKEN` (for example, a pull request from a fork).")
        # An annotation, so a skipped check never passes as quietly as a passing one.
        print("::warning title=EuKollab network checks skipped::No EKL_TOKEN: the network did not check agent.json.")
    if server:
        synced = run("sync", "--check", folder=folder, given=given)
        same = synced.returncode == 0
        failed |= not same
        lines += ["", "**Against your server and eukollab.json:** " + ("the same" if same else "different")]
        if not same:
            lines += ["", f"```\n{(synced.stdout + synced.stderr).strip()}\n```"]
    if not os.environ.get("EKL_TOKEN") and not server:
        # Neither check had what it needs: say so at the top, not as one line among results.
        lines[2:2] = [
            "**Nothing was checked.** Set `EKL_TOKEN` for the network's checks, or your server's address (`mcp`, "
            "`openapi` or `a2a`) to compare with it.",
            "",
        ]
        print("::warning title=EuKollab check-agent checked nothing::Neither EKL_TOKEN nor a server address was given.")
    return report(lines, failed=failed)


def report(lines: list[str], *, failed: bool) -> int:
    """The report to the log, the job summary and the pull request comment; the exit code."""
    text = "\n".join(lines) + "\n"
    print(text)
    for target in (os.environ.get("GITHUB_STEP_SUMMARY"), str(Path(os.environ["RUNNER_TEMP"]) / "eukollab-check.md")):
        if target:
            with Path(target).open("a") as out:
                out.write(text)
    shutil.rmtree(os.environ["EKL_CONFIG_DIR"], ignore_errors=True)  # the signed-in token goes with the job
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
