# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Working with FastAPI APIs, Pydantic models, dependencies, streaming responses incl. Server-Sent Events (SSE), serving frontend apps | fastapi | /home/mauro/.agents/skills/fastapi/SKILL.md |
| Writing or reviewing Python code with SQLModel: models, sessions, queries, FastAPI integration, relationships, link models, creates, updates, deletes | sqlmodel | /home/mauro/.agents/skills/sqlmodel/SKILL.md |
| Writing, reviewing or refactoring React components / pages, data fetching, bundle optimization, performance improvements | vercel-react-best-practices | /home/mauro/.agents/skills/vercel-react-best-practices/SKILL.md |
| Building new UI or reshaping existing UI: aesthetic direction, typography, distinctive visual design | frontend-design | /home/mauro/.agents/skills/frontend-design/SKILL.md |
| User says "diagnose"/"debug this", or reports something broken / throwing / failing / slow | diagnosing-bugs | /home/mauro/.agents/skills/diagnosing-bugs/SKILL.md |
| Automating a real browser from the terminal: navigation, form filling, snapshots, screenshots, data extraction, UI-flow debugging | playwright | /home/mauro/.agents/skills/playwright/SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### fastapi
- Always use `Annotated[..., Depends(...)]` style for params and dependencies; create reusable type aliases (e.g. `CurrentUserDep = Annotated[dict, Depends(get_current_user)]`)
- Never use `...` (Ellipsis) as default for required params or Pydantic fields; never use Pydantic `RootModel` — use `Annotated` + `Field`/`Body` with `TypeAdapter` semantics instead
- Prefer return-type annotations for response validation/filtering/serialization; use `response_model=` only when public schema differs from internal return value
- Never use `ORJSONResponse`/`UJSONResponse` (deprecated) — return types / response models handle Rust-side serialization
- Declare router-level `prefix`, `tags`, shared `dependencies=[Depends(...)]` on the `APIRouter`, not in `include_router()`
- One HTTP operation per function; default to sync `def` path operations unless the inner logic is fully async-safe (sync runs in threadpool, blocking code inside `async def` kills performance)
- SSE: `response_class=EventSourceResponse` + `yield` (`ServerSentEvent` for event/id/retry control); serve built frontends via `app.frontend()`/`router.frontend()`, not manual `StaticFiles`
- Prefer uv, Ruff, ty, Asyncer, SQLModel, HTTPX; run dev with `fastapi dev`, prod with `fastapi run`

### sqlmodel
- Prefer `sqlmodel` imports (`Field, Relationship, Session, SQLModel, create_engine, select`); never use SQLAlchemy declarative defaults (`declarative_base`, `Mapped`, `mapped_column`, `relationship`, `sessionmaker`) for normal SQLModel code
- Table models: `class X(SQLModel, table=True)` with `Field(default=None, primary_key=True)`; FK via `Field(foreign_key="team.id")`; separate non-table `SQLModel` classes for create/update/public schemas (`HeroBase`/`HeroCreate`/`HeroUpdate` all-optional for PATCH/`HeroPublic`)
- Timestamps (0.0.45+): plain `datetime` fields (auto `UTCDateTime`); write aware datetimes (`datetime.now(UTC)`), never naive `datetime.now()`/`utcnow()`; `AwareDatetime` to reject naive input (validate via `Model.model_validate`), `NaiveDatetime` only for intentional naive storage
- Sessions: `with Session(engine) as session:` + `session.exec(select(...))` (never `execute`/`query`, never append `.scalars()`); `session.get(Model, id)` for PK lookups; `.all()/.first()/.one()/.one_or_none()`; `add → commit → refresh` when DB defaults/IDs are needed
- Relationships via `Relationship(back_populates=...)` and `link_model=` for M2M (no ad-hoc `secondary=`); extra fields on link table → full model with direct link-object handling; new apps: keep related models in one file, else `TYPE_CHECKING` + string annotations
- Partial updates: `data = obj_update.model_dump(exclude_unset=True)` + `db_obj.sqlmodel_update(data)`; deletes/cascades via `cascade_delete=True` / `ondelete="CASCADE"` (nullable FK + `passive_deletes` for `SET NULL`)
- `SQLModel.metadata.create_all(engine)` only after all table models imported; SQLite needs `connect_args={"check_same_thread": False}`; `Field(sa_...)` escape hatches only when plain `Field()` can't express the column

### vercel-react-best-practices
- Eliminate waterfalls (CRITICAL): parallelize independent work with `Promise.all()`; start promises early, await late; check cheap sync conditions before awaiting; stream with `Suspense` boundaries
- Bundle size (CRITICAL): import directly, never barrel files; statically analyzable import paths; `next/dynamic` for heavy components; load third-party/analytics after hydration; preload on hover/focus
- Server: `React.cache()` per-request dedup + LRU for cross-request; minimize data passed to client components; hoist static I/O to module level; never keep mutable request state at module level in RSC/SSR; `after()` for non-blocking work
- Client fetching: SWR for request dedup; dedupe global listeners, passive listeners for scroll; versioned, minimal localStorage payloads
- Re-renders: don't subscribe to state only used in callbacks; derive during render, not in effects; primitive effect deps; `useState(() => expensive())` lazy init; never define components inside components; `startTransition`/`useDeferredValue` for non-urgent work; refs for transient high-frequency values
- Rendering/JS: ternary not `&&` for conditionals; `content-visibility` for long lists; hoist static JSX; batch DOM/CSS via classes; `Set`/`Map` for O(1) lookups; single-pass loops (`flatMap`, combined iterations); hoist RegExp out of loops; defer non-critical work to idle time

### frontend-design
- Ground every design in the subject/audience/job (here: Argentine dental practice — booking link + agenda); distinctive, opinionated palette/type/layout choices, never templated defaults
- Plan first as compact tokens (4–6 named hex colors, 1–2 typefaces with roles, layout concept with alignment, uniqueness principles); review plan against the brief and revise anything generic before coding
- Typography carries personality: 1–2 clearly distinct families, clear scale, <80ch line lengths; never accent a single headline word, never ALL-CAPS labels, never decorative eyebrows/labels above content
- Structure = information: borders/numbering/dividers only when they encode real meaning (numbers only for true sequences); watch CSS specificity collisions (e.g. `.section` vs `.cta` padding/margin)
- Motion answers action only (open/expand/confirm); one orchestrated moment max — never scattered fade-slide entrances or hover transitions on every card; respect reduced motion
- Copy is design: user vocabulary, active voice, CTA names the exact outcome ("Save changes"), same name across flow (button "Publish" → toast "Published"); errors explain what happened + how to fix, no apologies; empty states invite action
- Quality floor without announcing it: responsive to mobile, visible keyboard focus, accessible contrast; be bold in exactly one place, keep the rest quiet; avoid the generic tells (cream #F4F1EA + terracotta #D97757 serif hero, acid-green-on-black, hairline broadsheet, identical SaaS cards with rgba(0,0,0,.1) shadows, `A · B · C` meta strings, trailing `→`)

### diagnosing-bugs
- Phase 1 is the skill: build ONE tight, red-capable feedback loop before theorizing — failing test, curl/HTTP script, CLI invocation with snapshot diff, headless browser script, trace replay, throwaway harness, fuzz/property loop, `git bisect run` harness, or differential old-vs-new loop
- Loop must be: red-capable (asserts the user's exact symptom on the real code path), deterministic (pin time/seed/FS/network; flaky bugs: raise repro rate to ~50%+ via 100× loops/stress), fast (seconds), agent-runnable (already run once, invocation + output shown)
- No loop → stop: list what was tried, ask user for repro env, redacted artifact (HAR/log/dump/recording), or prod-instrumentation permission; never hypothesize without a loop
- Phase 2: reproduce (confirm it IS the user's failure) + minimize (cut inputs/callers/config one at a time until every remaining element is load-bearing); minimized repro becomes the regression test
- Phase 3: generate 3–5 ranked, falsifiable hypotheses ("If X is cause, then changing Y removes it / Z worsens it"); show the list to the user before testing, then proceed with your ranking
- Phase 4: one variable at a time; debugger/REPL first, then targeted boundary logs (never log-everything); tag all debug logs `[DEBUG-xxxx]` for single-grep cleanup; perf regressions: measure baseline + bisect, don't log-guess
- Phase 5: regression test BEFORE fix at a seam that exercises the real bug pattern (no correct seam → document it as the finding); fail → fix → pass → re-run original un-minimized loop
- Redact every secret as `<REDACTED>` (env vars, quote only signal lines); cleanup gate: original repro green, regression test passes, `[DEBUG-...]` removed, throwaways deleted, correct hypothesis stated in commit/PR message

### playwright
- CLI-first via wrapper script: `export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"` (needs `npx`; if missing, stop and ask user to install Node.js/npm); prefer wrapper over global install; never pivot to `@playwright/test` specs unless explicitly asked
- Core loop: `open <url>` → `snapshot` → interact with refs (`click/fill/type/press`) → re-snapshot after nav/major DOM change/modal/tab switch; refs go stale — on failure, snapshot again
- Always snapshot before using element ids (`e12`); on stale refs use placeholder `eX` and say why — never bypass refs with `run-code`/`eval` unless necessary; `--headed` when a visual check helps
- Form pattern: `open` → `snapshot` → `fill e1/e2 ...` → `click e3` → `snapshot`; multi-tab via `tab-new/tab-list/tab-select`; traces via `tracing-start` … `tracing-stop`
- Artifacts from this repo go to `output/playwright/` (no new top-level artifact folders); open only needed references (`references/cli.md`, `references/workflows.md`)

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| (none) | — | No CLAUDE.md / AGENTS.md / agents.md / .cursorrules / GEMINI.md / copilot-instructions.md at project root yet (agent-instruction phase runs next and will generate them from this registry + knowledge-base) |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
