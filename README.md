# eukollab/check-agent

Checks an EuKollab agent's `agent.json` in a GitHub workflow. It changes nothing: it never syncs, deploys, registers
or confirms, and never writes `agent.json`. A new version of your agent reaches the network only when you confirm it.

```yaml
- uses: actions/checkout@v4
- uses: eukollab/check-agent@v1
  with:
    file: agent.json
  env:
    EKL_TOKEN: ${{ secrets.EKL_TOKEN }}
```

`EKL_TOKEN` is a CI token: create one in the console under Account → Team → Developer access. It can only
check agent files; it can't view your agents, change them or act on the network.

## What it checks

- **The network's checks.** `ekl check`, run in the folder of `file`: what the network would refuse or warn about in
  `agent.json`, and whether the services your agent plans to use are still listed and match the schemas they were planned against. With `mcp`
  set, it also tries each example in `agent.json` on your server.
- **The file against your server**, when you give `mcp`: start your MCP server earlier in the job and pass its address.
  `ekl sync --check`, run in the same folder with `EKL_UPSTREAM_MCP_URL` set to that address, fails when `agent.json`
  differs from what your server and `eukollab.json` give.

On a pull request from a fork, GitHub gives no secrets. With `mcp` it then runs the second check alone; either way
the job summary says the network's checks were skipped and the run carries a warning annotation. With neither
`EKL_TOKEN` nor `mcp`, nothing is checked: the summary opens with **Nothing was checked** and the run is marked with a
warning, so a skipped check never looks like a pass. The job itself still succeeds, so fork pull requests aren't
blocked.

## Inputs

| Input | Default | What it is |
|---|---|---|
| `file` | `agent.json` | The `agent.json` to check, in the agent's folder |
| `mcp` | none | Your MCP server's address, started earlier in the job |
| `platform` | `https://eukollab.ai` | The EuKollab network |
| `comment` | `false` | On a pull request, keep one comment with the results up to date (needs `pull-requests: write`) |

The results are also in the job summary. In other CI systems, run the same commands: `ekl login` with `EKL_TOKEN` set,
then, in the agent's folder, `ekl --json check` and `ekl sync --check`, with `EKL_UPSTREAM_MCP_URL` set to your
running server for the examples and its tools.

How to create the token and what each check reports: <https://eukollab.ai/docs/guide/check-in-ci>.

## Licence

Copyright © 2026 EuKreate, Inc. Licensed under the [Apache License 2.0](LICENSE); see [NOTICE](NOTICE).

EuKollab™ is a trademark of EuKreate, Inc.
