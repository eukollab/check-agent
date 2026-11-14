# Copyright © 2026 EuKreate, Inc.
# SPDX-License-Identifier: Apache-2.0
"""The Action's checks: the network's checks of agent.json with a CI token, and, given the server's
address, whether agent.json still matches what the server declares. It writes nothing but its report."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["ekl", *args], capture_output=True, text=True, check=False)


def answered_problems(checked: subprocess.CompletedProcess[str]) -> list[dict[str, str]] | None:
    """The problems `ekl --json agent check` reported, or None when the command failed or its answer isn't one."""
    if checked.returncode != 0:
        return None
    try:
        answer = json.loads(checked.stdout)
    except json.JSONDecodeError:
        return None
    problems = answer.get("problems") if isinstance(answer, dict) else None
    if not isinstance(problems, list) or not all(isinstance(p, dict) for p in problems):
        return None
    return problems


def diagnostics(done: subprocess.CompletedProcess[str]) -> str:
    """What the command said, for the report: its exit code and output, cut to a readable length."""
    said = (done.stderr.strip() + "\n" + done.stdout.strip()).strip() or "no output"
    return f"exit code {done.returncode}\n{said[:2000]}"


def main() -> int:
    file, mcp, platform = os.environ["FILE"], os.environ.get("MCP", ""), os.environ["PLATFORM"]
    lines = [f"### EuKollab check of `{file}`", ""]
    failed = False
    if os.environ.get("EKL_TOKEN"):
        login = run("login", "--platform", platform)
        if login.returncode != 0:
            lines += ["**Could not sign in with `EKL_TOKEN`:**", "", f"```\n{login.stderr.strip()}\n```"]
            failed = True
        else:
            checked = run("--json", "agent", "check", file)
            problems = answered_problems(checked)
            if problems is None:
                # A failed command or an answer without its problems list is a failure, never a pass.
                failed = True
                lines += ["**The network's checks could not run:**", "", f"```\n{diagnostics(checked)}\n```"]
            else:
                errors = [p for p in problems if p.get("level") == "error"]
                failed |= bool(errors)
                lines.append("**The network's checks:** " + ("problems found" if errors else "passed"))
                lines += [f"- {p.get('level')}: `{p.get('field') or '-'}` {p.get('message', '')}" for p in problems]
    else:
        # GitHub gives no secrets to a pull request from a fork.
        lines.append("**The network's checks were skipped:** no `EKL_TOKEN` (for example, a pull request from a fork).")
        # An annotation, so a skipped check never passes as quietly as a passing one.
        print("::warning title=EuKollab network checks skipped::No EKL_TOKEN: the network did not check agent.json.")
    if mcp:
        synced = run("agent", "sync", file, "--mcp", mcp, "--check")
        same = synced.returncode == 0
        failed |= not same
        lines += ["", "**Against the server's declarations:** " + ("the same" if same else "different")]
        if not same:
            lines += ["", f"```\n{(synced.stdout + synced.stderr).strip()}\n```"]
    if not os.environ.get("EKL_TOKEN") and not mcp:
        # Neither check had what it needs: say so at the top, not as one line among results.
        lines[2:2] = [
            "**Nothing was checked.** Set `EKL_TOKEN` for the network's checks, or `mcp` to compare with your server.",
            "",
        ]
        print("::warning title=EuKollab check-agent checked nothing::Neither EKL_TOKEN nor mcp was given.")
    report = "\n".join(lines) + "\n"
    print(report)
    for target in (os.environ.get("GITHUB_STEP_SUMMARY"), str(Path(os.environ["RUNNER_TEMP"]) / "eukollab-check.md")):
        if target:
            with Path(target).open("a") as out:
                out.write(report)
    shutil.rmtree(os.environ["EKL_CONFIG_DIR"], ignore_errors=True)  # the signed-in token goes with the job
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
