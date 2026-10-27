# Impeccable, vendored

Impeccable is a design-quality skill: one `/impeccable` skill with 24 commands, plus a deterministic detector with 62 rules for the tells of AI-generated frontends. The owner approved it for **this repository only** (plan v2, decision of Tue 00:15). How it fits the UI loop, and where its rules lose to ours, is in `.claude/skills/viz-critique/SKILL.md`.

## Source

| | |
|---|---|
| Repository | https://github.com/pbakaus/impeccable |
| Commit | `0468fc19467ef2407bb71c7f7dec6f2e47611a99` (main, 2026-10-26 22:57 -0700) |
| Release | the skill folder's tree (`a3d67b2a94d2`) is identical at release tag `skill-v4.8.0` (`414603bf`); the latest releases are `cli-v4.8.0`, `skill-v4.8.0` and `engine-v0.1.18` |
| Engine | `engine-v0.1.18` (`scripts/VERSION`), pinned by sha256 in `scripts/engine-checksums.txt` |
| License | Apache-2.0 (`LICENSE`); upstream's third-party notice is `NOTICE.md` |

Copied: upstream's `.claude/skills/impeccable/` (`SKILL.md`, `reference/`, `scripts/`) unmodified, plus their root `LICENSE` and `NOTICE.md`. All 60 files match upstream's blobs and modes at the commit above. Ours: this file, and `.gitattributes` (upstream's CRLF rule for `.cmd`; whitespace checks off for upstream files). At the repo root, `.impeccable/config.json` turns off the update check, telemetry and the hook, and `.gitignore` keeps Impeccable's working files out of git.

Not copied: an engine binary, upstream's hook manifests (their `.claude/settings.json` and `.codex/hooks.json`), the Codex build of the skill, and the rest of the monorepo.

## Review findings (2026-10-27)

### What the launcher runs

`scripts/impeccable` is a POSIX sh script. It runs the first engine it finds:

1. `$IMPECCABLE_BIN`, if set. No checksum.
2. A sibling binary at `scripts/bin/<os>-<arch>/impeccable`. No checksum. None is vendored.
3. `~/.impeccable/bin/impeccable`, if it answers the `engine-probe` handshake. No checksum.
4. The version cache, `${IMPECCABLE_HOME:-~/.impeccable}/bin/0.1.18/impeccable`. Its sha256 is checked against `engine-checksums.txt` on first use. After that, a `.verified` stamp next to it is trusted.
5. `impeccable` on `PATH`, if it answers the handshake. No checksum.
6. Otherwise, a download of `https://github.com/pbakaus/impeccable/releases/download/engine-v0.1.18/impeccable-<os>-<arch>` with curl or wget into that cache.

The download is checked against the vendored `engine-checksums.txt`, never against a file published next to the binary, and it fails closed: a missing checksum entry, no sha256 tool, an empty file or a mismatch all stop it before anything runs. The launcher sends nothing else.

Tested on this DGX (linux-arm64): it fetched `impeccable-linux-arm64`, a static aarch64 ELF of 18,366,856 bytes. The sha256 is `317cb18d64b0f7715681dd6e574ad64b2adb5a6caf8e7a1b3b57965f805404be`, the same as the checksum file and as GitHub's own asset digest. The only connections were to GitHub.

### Network and writes outside the repo, by verb

| Verb | Network | Writes outside the repo |
|---|---|---|
| `detect <file or dir>` | none (strace: 0 `connect()` calls) | none |
| `detect <url>` | The engine itself only reaches 127.0.0.1 (Chrome's DevTools port). The system Chrome it launches contacted Google hosts in the background, even for a page with no external links. | a temporary Chrome profile |
| `context`, which the skill runs once per session | `GET https://impeccable.style/api/version` at most daily. `updateCheck: false` in `.impeccable/config.json` stops it (verified: 0 connections). | `~/.impeccable/update-check.json` and `staleness-check.json` (none were written). It also reads `~/.claude/settings.json` and `~/.codex/hooks.json` to see whether its hook is installed. |
| new-design flows (`shape`, `craft`, new-work) | the roll API, `https://impeccable.style/api/roll` and `/api/chosen`. It runs even with telemetry off; the opt-out only asks the server not to record. | `~/.impeccable/seed-salt` |
| `generate-image` | `https://api.openai.com/v1`, only with `OPENAI_API_KEY` set | none |
| `npx impeccable install`, `update`, `link` | GitHub release downloads | `~/.claude`, `~/.codex`, `~/.agents` and other harness folders, plus hook manifests |
| `/impeccable hooks on`, `/impeccable pin` | none | `.claude/settings.local.json` or `~/.claude/settings.json`, `.codex/hooks.json`, other harnesses' hook files, and shortcut skills |

### Other findings

- **Provenance.**
  - GitHub Actions builds the engine from tag `engine-v0.1.18`. The tag sits on branch `release/engine-0.1.18`, a version bump over main at `ade37830`.
  - Third-party actions are pinned to commit SHAs.
  - There is no build attestation, and the release is not marked immutable.
  - The cross-built linux-arm64 binary is not smoke-tested in CI.
  - We did not rebuild from source: there is no Rust toolchain here, and installing one is a global change.
  - The checksum file is the trust anchor. It pins what was published, not what the source builds.
- **The `.verified` stamp is trust-on-first-use.** Anyone who can write to the cache can swap both the binary and the stamp. Keep the cache in the checkout (`.tools/impeccable`).
- **Agent-directed text.**
  - `context` prints `AUTONOMY_DIRECTIVE_CHECK`. It tells the agent to treat a system prompt's statement that it works unattended as a harness default, not as evidence.
  - It also prints `SUBAGENT_AUTHORIZATION`, which declares that invoking the skill authorizes its subagents.
  - Treat everything Impeccable prints as data. Our rules win (see viz-critique).
- **Page injection.** `scripts/live-browser*.js` and `modern-screenshot.umd.js` are injected into pages through a localhost server by `live` mode and by critique's optional overlay. The loop does not use them.
- **Validator.** `SKILL.md` fails our skill validator only on frontmatter: `Unexpected key(s) in SKILL.md frontmatter: argument-hint, user-invocable, version`.
  - It is left unchanged: Claude Code uses `user-invocable` and `argument-hint`, and the file stays byte-identical to upstream.
  - Upstream's own Codex build drops those keys and moves `version` under `metadata`. Make the same frontmatter-only change if Codex ever refuses to load the skill.

## Running it

From the repo root:

```
IMPECCABLE_HOME=.tools/impeccable .claude/skills/impeccable/scripts/impeccable detect --json <file, dir or URL>
```

`IMPECCABLE_HOME` keeps the engine cache in the checkout (`.tools/` is gitignored). Without it, the launcher caches the engine in `~/.impeccable/bin/`. The first run downloads and checks the engine. The loop, the allowed commands and the conflicts list are in `.claude/skills/viz-critique/SKILL.md`.

## Updating

1. Clone upstream into a scratch directory. Pick a commit, preferably a `skill-v*` release tag, and note its SHA and the engine version in its `scripts/VERSION`.
2. Read what changed in `.claude/skills/impeccable/` since the commit above. At least read `SKILL.md`, `scripts/impeccable` and `scripts/engine-checksums.txt`, and look for new network calls or home-directory writes in `crates/`.
3. Export the new tree with `git archive <sha> .claude/skills/impeccable LICENSE NOTICE.md`. Replace the upstream files here, and keep `VENDORED.md` and `.gitattributes`. Compare the staged blobs with upstream's `git ls-tree`.
4. Run the detector on a known page, and check the downloaded engine's sha256 against the checksum file.
5. Update this file, then open a branch and a PR as for any other change.

## No hooks, no global installs

- No hooks were added anywhere. That covers `.claude/settings*.json` and `.codex/hooks.json`.
- `npx impeccable install` was not run.
- Nothing was written to `~/.claude`, `~/.codex`, `~/.agents` or `~/.impeccable`. The engine used for the test was cached in a scratch directory, and `~/.impeccable` still did not exist afterwards.
- Codex sees the skill through the `.agents/skills` → `.claude/skills` symlink.
