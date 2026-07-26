# Contextual Dreamwork plugin loading

## What changed

`ud-dreamwork-*` plugins no longer belong in ordinary harness skill-discovery
roots. Their source packages keep valid `SKILL.md` frontmatter, but inactive
Dreamwork contributes neither plugin descriptions to model prompts nor
`/skill:<plugin>` commands to users.

An active loop now treats exact `- Load: `ud-dreamwork-…`` entries under the
target's `DREAMWORK.md` Plugins section as the complete declaration set.
`plugin_resolver.py` resolves only bounded inputs from bundled packages,
canonical sibling packages, exact explicit files, and controlled roots. It
validates matching frontmatter and fails on missing/invalid/ambiguous entries.
Initialization reads emitted `SKILL.md` paths directly.

## How to apply

1. Update the Dreamwork core and prove every recorded Load declaration resolves
   **before** touching any old discovery link:

   ```sh
   python3 <skill-dir>/plugin_resolver.py --target <target> \
     > /tmp/dreamwork-active-plugins.json
   ```

   Add `--path <id>=</path/to/SKILL.md>` for one intentional noncanonical
   package, or `--root <package-parent>` for a controlled parent. Inspect the
   bounded JSON and read/follow each emitted `SKILL.md`. Do not continue if
   resolution fails.

2. Inventory **every** plugin currently registered through the known ordinary
   roots (`~/.pi/agent/skills`, `~/.agents/skills`, `~/.claude/skills`, and
   `~/.claude-p/skills`) without changing them:

   ```sh
   python3 <skill-dir>/hide_plugins.py --check --target <target> \
     --additional-root <configured-package-or-settings-skill-root> \
     --inventory-out /tmp/dreamwork-plugin-preservation.json
   ```

   Repeat `--additional-root` for **every** skill root supplied by enabled Pi
   packages, the `skills` settings array, or the session's `--skill` CLI flags.
   These are runtime configuration, not universally enumerable filesystem
   locations; omitting one makes the migration incomplete. Defaults cover Pi's
   two global roots, the target/ancestor `.pi/skills` and `.agents/skills` roots
   up to its repository boundary, and the installed Claude compatibility roots.

   Exit 1 means validated discovery symlinks remain; inspect the emitted
   preservation manifest. Exit 0 means no links remain (the schema-v1 object's
   `plugins` array is `[]`).
   Exit 2 is unsafe state and writes no manifest. The helper will **refuse**
   real package directories/files, unreadable or mismatched links, two distinct
   source packages for one ID, and any source package located inside a discovery
   root. Inventory follows Pi's recursive skill-directory semantics (bounded to
   10,000 entries and depth 32), so nested aliases cannot evade the post-check.
   Move/copy such a source to bundled, canonical sibling, or explicit storage
   first, then rerun both steps. This inventory includes undeclared and
   negatively-declared packages: unlink must never be their only surviving
   source.

3. Only after both manifests have been inspected, remove the exact aliases from
   the preservation manifest and prove the ordinary inventory is empty:

   ```sh
   python3 <skill-dir>/hide_plugins.py --target <target> \
     --additional-root <each-configured-root> \
     --manifest /tmp/dreamwork-plugin-preservation.json
   python3 <skill-dir>/hide_plugins.py --check --target <target> \
     --additional-root <each-configured-root> \
     --inventory-out /tmp/dreamwork-plugin-postcheck.json
   ```

   Apply first rebuilds the current inventory and requires exact semantic
   equality with the inspected manifest, including schema, roots, plugin IDs,
   preserved source paths, and every alias path. Any addition, omission,
   retargeting, malformed entry, or other drift fails before mutation. Accepted
   aliases are staged through reversible same-directory renames; an unlink
   failure restores the aliases rather than leaving a partial migration.

   The second command must exit 0 and its `plugins` array must be empty.
   Restart/reload each harness so its startup inventory is rebuilt. Verify with
   Pi's real `DefaultResourceLoader` using the target cwd, agent dir, enabled
   packages/settings paths, and CLI skill paths from the migrated session; no
   `ud-dreamwork-*` name may remain. An already-running session may retain stale
   startup entries until reload; that process state is not an active-loop
   loading mechanism. A future session that explicitly supplies a new CLI root
   can of course reintroduce a plugin and must migrate that newly enumerated root.

4. Write `2026-07-26-02-contextual-plugin-loading.md` to
   `.dreamwork/skill-version` only after active declarations resolve, the
   preservation manifest has been applied, and the post-check is empty.
