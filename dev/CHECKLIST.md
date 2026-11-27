# Quick checklist (from "The Complete Guide to Building Skills for Claude", Reference A)

Each item has the evidence behind it. "Automated" means `dev/scripts/validate_skill.py` or a test checks it on every push.

## Before you start
| Item | Status | Evidence |
|---|---|---|
| Identified 2-3 concrete use cases | ✅ | SKILL.md Examples 1-3: build from the owner's documents, practice run, add hybrid search |
| Tools identified (built-in or MCP) | ✅ | Built-in only: file system, bash, Python. No MCP is needed. The `compatibility` field states this |
| Reviewed this guide and example skills | ✅ | Structure follows Chapters 2 and 5. Links are in `references/resources.md` |
| Planned folder structure | ✅ | `SKILL.md`, `scripts/`, `references/`, `assets/` (guide's file structure) |

## During development
| Item | Status | Evidence |
|---|---|---|
| Folder named in kebab-case | ✅ automated | `rag-prototype-builder` |
| SKILL.md file exists (exact spelling) | ✅ automated | |
| YAML frontmatter has --- delimiters | ✅ automated | parsed with `yaml.safe_load` |
| name field: kebab-case, no spaces, no capitals | ✅ automated | matches the folder name. No reserved words |
| description includes WHAT and WHEN | ✅ automated | 772 chars (under 1024). Has trigger phrases, file types and negative triggers ("Do NOT use for ...") |
| No XML tags (angle brackets) anywhere | ✅ automated | frontmatter, SKILL.md and all `references/` are checked. `assets/` holds templates (HTML, SQL), not instructions |
| Instructions are clear and actionable | ✅ | Numbered steps with exact commands, expected output and a **Gate** for each step. Critical rules come first |
| Error handling included | ✅ automated | Troubleshooting table in SKILL.md, plus `references/troubleshooting.md` |
| Examples provided | ✅ automated | 3 examples, each with what the user says, the actions and the result |
| References clearly linked | ✅ automated | Every reference file is linked from SKILL.md, with when to read it. Every linked path exists |
| No README.md in the skill folder | ✅ automated | The template's readme ships as `README.template.md`. `scaffold.py` renames it |
| SKILL.md under 5,000 words | ✅ automated | about 1,600 words. Detail lives in `references/` (progressive disclosure) |
| Critical validations done by code, not language | ✅ | `rag-prototype-builder/scripts/check_rules.py`, tested against 7 planted violations |

## Before upload
| Item | Status | Evidence |
|---|---|---|
| Tested triggering on obvious tasks | ✅ 4/4 | `dev/evals/run_trigger_tests.py` (headless Claude Code), run on 2026-11-26, saved in `dev/evals/results/triggers-20261126-2034.json` |
| Tested triggering on paraphrased requests | ⚠️ 3/4 | The first run scored 2/4. Following the guide's undertriggering fix, keywords were added to the description. Still missed: "Add evals with hit@k and MRR to my document retrieval prototype": Claude first searched the empty test folder for the prototype and hit the 2-turn limit. Overall 7/8 relevant prompts = 87.5%, against the guide's 90% target |
| Verified doesn't trigger on unrelated topics | ✅ 6/6 | same run |
| Functional tests pass | ✅ | `dev/scripts/test_template.sh`: scaffolded app, 5/5 CI stages, 26 tests, rule check passed. `dev/tests/`: 14 passed |
| Tool integration works (if applicable) | n/a | No MCP. The bundled scripts run in the functional test |
| Compressed as .zip file | ✅ | `dev/scripts/package.sh` builds `dist/rag-prototype-builder.zip` after validation. CI uploads it as an artifact |

## After upload (ongoing)
| Item | How |
|---|---|
| Test in real conversations | Scenarios in `dev/evals/functional.md`, each run 3-5 times |
| Monitor for under/over-triggering | Re-run `dev/evals/run_trigger_tests.py` after every description change. Add misfires to `dev/evals/triggers.json` |
| Collect user feedback | GitHub Issues on this repo |
| Iterate on description and instructions | Use the guide's signals: undertriggering means adding keywords; overtriggering means adding negative triggers |
| Update version in metadata | `metadata.version` in SKILL.md (semver, checked automatically) plus `dev/CHANGELOG.md` |
