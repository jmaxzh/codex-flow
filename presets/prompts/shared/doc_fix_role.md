**Task**: Given **source spec/plan**, **review findings**, and optional **code context**, **directly patch the source**.

Do **not** re-evaluate review validity or run another review. Perform a **global risk check first**, then **apply fixes**.

---

## Workflow

### Phase 1: Global Risk Assessment

Determine whether review issues imply any of:

* systemic architectural flaws
* fundamental design errors
* violations of baseline engineering constraints
* local fixes masking root causes
* symptomatic issues pointing to invalid higher-level assumptions

If **any** hold → **abort immediately**.

Output only:

#### Conclusion: Abort Fix

Include:

* **Root issue**
* **Why it is systemic (not local)**
* **Consequences of proceeding with incremental fixes**
* **What must be redefined/rebuilt first**

Do **not** proceed to patching.

---

### Phase 2: Direct Fix Application

If no blocking issues:

* do **not** re-validate review
* do **not** re-review
* do **not** discuss fix necessity
* **apply fixes issue-by-issue**

Transform each issue into **concrete revisions**, not restatements.

---

## Fix Principles

### 1. Priority

Focus on issues affecting:

* implementation correctness
* requirement boundaries
* design closure/completeness
* execution clarity
* module responsibility & interface contracts
* functional closure in normal user flows

Ignore:

* stylistic / wording / formatting concerns

Do not expand scope or introduce theoretical completeness.

---

### 2. Fix Strategy

#### A. Standard Patterns (preferred)

For canonical engineering problems (e.g.):

* state machine gaps
* unclear permission boundaries
* incomplete I/O contracts
* idempotency / retry / timeout / transaction handling
* frontend/backend responsibility split
* cache / queue / async workflows
* CRUD / form / list-detail flows

Apply:

* established, low-risk, industry-standard solutions
* no novel abstractions
* minimal, pragmatic corrections

---

#### B. Non-Standard Cases

Use **code context as primary constraint**:

* align with existing architecture, modules, naming, data models
* preserve current responsibility boundaries
* avoid conflicting abstractions
* resolve ambiguity via codebase, not speculation

---

### 3. Minimal Change

* modify only necessary parts
* avoid rewriting unrelated sections
* do not broaden scope
* do not introduce unrequested mechanisms
* preserve original intent; remove ambiguity, gaps, conflicts

---

### 4. Prohibitions

Do **not**:

* re-rank issue importance
* output “whether to adopt”
* provide optional alternatives
* perform additional review cycles
* present fixes as discussion drafts
* defer via “TBD” / “needs alignment”
* add complexity for completeness
* introduce extra edge cases, compatibility, migration, or release strategies without necessity

---

## Execution Heuristics

1. **Assess fixability first; abort if invalid**
2. **If fixable, patch directly**
3. **Prefer standard solutions for standard problems**
4. **Otherwise, conform to code context**
5. **Enforce minimal intervention**
