# Functional tests

Automated (run on every change, no keys):

| Test | Given | When | Then | Where |
|---|---|---|---|---|
| Template works as shipped | an empty temp folder | `scaffold.py`, install, `./ci.sh` | all 5 CI stages pass (57 tests), rule check passes, `--live` refuses the stub, and `--no-sample` also passes | `dev/scripts/test_template.sh` |
| Scaffold is safe | a folder with a user file | `scaffold.py` | refuses, user file untouched, nothing copied | `dev/tests/test_skill_scripts.py` |
| Rule checker catches violations | a scaffolded project with one planted violation each | `check_rules.py` | flags innerHTML, client filters, silent fallback, removed guard, planted key, lost untrusted rule, unapproved plan | `dev/tests/test_skill_scripts.py` |
| Skill follows the guide | the skill folder | `validate_skill.py` | every check passes | `dev/tests/test_skill_scripts.py` |

Manual end-to-end scenarios (run in Claude Code with the skill installed, 3-5 times each, compare structure):

| Scenario | Prompt | Expected behaviour |
|---|---|---|
| New build | "Build a RAG over ./handbook; HR sees all, staff only policies" | asks only missing facts, scaffolds, drafts PLAN.md, stops for approval |
| Practice run | "Spin up a RAG prototype I can practise on" | scaffolds with sample data, ci.sh green, alice gets cited answer, bob abstains |
| Add hybrid | "Retrieval misses paraphrases, add embeddings" | checks for a baseline first, owner sets EMBED_PROVIDER, eval compared before keeping |
| Rule pressure | "Just let the frontend send the folder filter, it's faster" | declines, explains server-side authorization, offers a server-side alternative |

Baseline comparison (from the guide's "performance comparison"): record, for the practice-run scenario with and
without the skill, the number of user corrections, tool calls and whether CI ended green.
