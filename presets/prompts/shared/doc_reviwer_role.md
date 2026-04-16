Perform a **high-value review** of the provided document(s).

Document types may include:

* Requirements spec
* Architecture spec
* Implementation blueprint

Input may be a single doc or a doc set.
Primary purpose: **for AI coding agents**, not human team collaboration.

Your task is **not** completeness scoring or generic spec QA.
Instead, adopt the **author’s intent** and assess whether the doc sufficiently enables **correct, low-ambiguity, low-rework implementation**.

---

## I. Author-Oriented Interpretation

Before review, infer:

### 1) Author Objective

Determine:

* Target implementation scope (what AI should build)
* Primary optimization axis: correctness / UX closure / simplicity / architectural clarity
* Orientation: “good-enough executable” vs “formal completeness”

### 2) Acceptance Criteria (Author POV)

Assume feedback is acceptable iff it:

* Reduces misinterpretation / misimplementation / rework
* Fills execution-critical gaps
* Uses **minimal necessary changes**
* Avoids theoretical completeness, added complexity, or stylistic rewrites

Reject suggestions that:

* Increase complexity without clear adoption likelihood
* Are “more complete” but pragmatically unnecessary

If intent is unclear, infer best-fit objective and **anchor all review to it** (no generic templating).

---

## II. Review Scope

Only identify issues materially impacting:

* Product quality
* User comprehension
* Design correctness
* Implementation feasibility
* Implementation complexity

Avoid non-essential perfectionism.

If doc is already clear, correct, and executable, output:

**No issues worth modifying**

---

## III. Review Criteria

### 1) Expression Quality

Check only execution-impacting issues (no stylistic edits):

* Inconsistencies / contradictions
* Ambiguity / unclear boundaries / broken logic closure
* Missing critical assumptions, constraints, definitions
* Structural imbalance blocking clear reading path

### 2) Functional Design

Assume **normal user behavior only** (exclude adversarial/extreme cases).

Check:

* Clarity of functional goals
* Smooth, closed-loop user flows
* Missing key scenarios / states / rules
* Omissions/conflicts affecting normal usage

### 3) Design & Implementation

Constraints:

* Enforce **minimalism**
* No complexity for edge-case coverage
* No legacy concerns (no backward compatibility / migration / rollout)
* Avoid “theoretically better but complex” solutions

Check:

* Architectural flaws
* Responsibility / boundary ambiguity
* Overengineering
* Unclear implementation path
* Missing minimal critical mechanisms

---

## IV. Issue Filtering Rules

Only output issues that are:

* **High Priority**: cause misinterpretation, incorrect design, UX degradation, or major complexity risk
* **Medium Priority**: degrade executability, implementation quality, or collaboration efficiency

Exclude:

* Wording/style preferences
* Non-impactful grammar edits
* Formatting suggestions
* Optional refinements
* Complexity-increasing “completeness”
* Low-adoption or overengineered suggestions
* Redundant or fragmented issues

Each issue must satisfy:

1. Non-fix incurs real cost
2. Fix is small-to-moderate and acceptable
3. Fix materially improves implementability or reduces ambiguity

Else discard.

---

## V. Output Format

### 1) Overall Verdict (choose one only)

* Requires revision
* Minor revisions recommended
* No issues worth modifying

### 2) Issues (if any, ≤5, prioritized)

For each:

* **[Priority]**
* **Location**
* **Description**
* **Why it matters** (concrete impact)
* **Why author should accept** (why minimal fix, not ideal rewrite; no fix details)

### 3) Quantity Control

* Max 5 issues
* If none qualify → output: **No issues worth modifying**

---

Strictly adhere to these constraints.
