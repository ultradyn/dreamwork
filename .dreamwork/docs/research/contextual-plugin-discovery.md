# Contextual discovery for `ud-dreamwork-*` plugins

**Task:** #267  
**Date:** 2026-07-26  
**Question:** How can Dreamwork plugins remain unavailable to ordinary users and models, yet load predictably when the Dreamwork loop is active?

## Recommendation

Do not publish Dreamwork plugin directories into ordinary harness skill-discovery roots. Keep valid Agent Skills frontmatter in each source package, but have the active `ud-dreamwork` core resolve only the plugins named by the target's `DREAMWORK.md` and read their `SKILL.md` files directly from deterministic install-relative paths.

This is the smallest portable design that meets both requirements:

- an inactive Dreamwork installation contributes no plugin names/descriptions to the model prompt and no `/skill:<plugin>` commands to users;
- the active core can still validate and load a named plugin as ordinary text, independent of harness-specific dynamic registration.

## Primary-source findings

### Ordinary discovery always registers a skill

Pi recursively discovers directories containing `SKILL.md` under global, project, package, settings, and CLI skill locations. At startup it includes each discovered skill's name and description in the model system prompt; it also registers `/skill:name` commands. Therefore the current symlinks under `~/.pi/agent/skills/` and `~/.agents/skills/` make every Dreamwork plugin globally visible even when Dreamwork is inactive.

Source: Pi `docs/skills.md`, “Locations”, “How Skills Work”, and “Skill Commands”:
`/home/xertrov/.local/share/pnpm/global/5/.pnpm/@earendil-works+pi-coding-agent@0.81.1_ws@8.21.0_zod@4.4.3/node_modules/@earendil-works/pi-coding-agent/docs/skills.md`.

### `disable-model-invocation` is only a partial fit

Pi's optional `disable-model-invocation: true` frontmatter hides the skill from the system prompt, but explicitly requires user invocation through `/skill:name`. It removes recurring model-context cost while retaining exactly the ordinary user-facing surface the human asked to remove.

Source: Pi `docs/skills.md`, “Frontmatter”.

### Dynamic skill discovery still registers the result

A Pi extension may contribute `skillPaths` during `resources_discover`, including on reload. This changes *when* a skill is discovered, not what discovery means: the contributed path becomes a normal registered skill with prompt/command semantics. It also introduces a Pi-specific TypeScript extension lifecycle and installation dependency.

Source: Pi `docs/extensions.md`, “Resource Events → resources_discover”:
`/home/xertrov/.local/share/pnpm/global/5/.pnpm/@earendil-works+pi-coding-agent@0.81.1_ws@8.21.0_zod@4.4.3/node_modules/@earendil-works/pi-coding-agent/docs/extensions.md`.

Pi's dynamic tool loading is not a skill solution. It registers tools up front, keeps some inactive, and activates their definitions later; Dreamwork plugins are instructional files, not tool schemas.

Source: Pi `docs/extensions.md`, “Dynamic Tool Loading”.

### MCP/provider machinery adds no relevant capability

Pi provider registration configures model providers, not instructional resources. MCP would require separate integration and still offer no advantage over reading a trusted local text file. The active Dreamwork core already knows when plugin resolution is required and can read the plugin directly.

Sources: Pi `docs/extensions.md`, “registerProvider”; Pi README's MCP discussion.

## IGC evaluation

**Context:** plugins are trusted local instructional packages; the same repository supports multiple agent harnesses; only an active Dreamwork loop needs them.

- **G1:** absent from ordinary model prompt and user skill commands.
- **G2:** deterministic loading by an active Dreamwork loop.
- **G3:** portable across harnesses without a runtime integration service.
- **G4:** preserves validation, packaging, and actionable missing-plugin errors.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| `disable-model-invocation` + current symlinks | ✘ | ✘ | ✔ | ? | ✔ |
| Pi extension `resources_discover` | ✘ | ✘ | ✔ | ✘ | ✔ |
| MCP/dynamic provider | ✘ | ? | ✔ | ✘ | ✘ |
| No discovery symlinks; active core reads deterministic paths | ✔ | ✔ | ✔ | ✔ | ✔ |
| Leave current global discovery unchanged | ✘ | ✘ | ✔ | ✔ | ✔ |

Decisive errors:

- hidden frontmatter keeps `/skill:name`, failing G1;
- `resources_discover` still registers the skill and is Pi-specific, failing G1/G3;
- MCP/provider machinery introduces an unrelated service/interface and no standard skill-loading benefit, failing G3/G4;
- current discovery fails G1 and spends prompt context every session.

## Proposed loader contract for #268

1. `DREAMWORK.md` remains the target's declaration of plugin IDs.
2. The active core maps each validated ID to explicit candidate paths, preferring bundled `plugins/<id>/SKILL.md` relative to the installed core and then a documented canonical sibling package root.
3. It reads only declared plugins; it never recursively scans ordinary global skill roots.
4. It validates readable `SKILL.md` plus matching `name` frontmatter before following the plugin.
5. Missing or ambiguous plugins fail loudly with searched paths and installation guidance.
6. Install/update removes global discovery symlinks only after the direct loader and migration verification are available.

## Non-goals

- No dynamic tool registration.
- No MCP server.
- No model-provider changes.
- No removal of Agent Skills frontmatter from source packages.
- No attempt to conceal plugin source from a model that the active Dreamwork core has deliberately instructed to read it.
