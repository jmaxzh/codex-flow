**Refactor Pre-Review Compression Prompt**

---

Your task is **not exhaustive critique**, but to infer the **author’s primary refactor intent**, then output only **high-acceptance, high-ROI improvements**.

---

### 1. Infer Author Intent (priority heuristics)

From code signals, deduce likely goal:

* Duplicate logic → **deduplication, branch convergence, lower maintenance cost**
* Deep nesting / complex conditionals → **flatten control flow, improve readability**
* Repeated traversal / redundant state → **streamline data pipeline, eliminate waste**
* Already fine-grained functions → **optimize structure clarity, not further decomposition**
* Conservative style → favor **low-risk, high-impact incremental changes**

If unclear, default to:
**reduce duplication, complexity, and indirectness without behavior change**

---

### 2. Filter for Acceptable Suggestions

Only include suggestions that:

* Align with inferred intent
* Preserve behavior, I/O, and external semantics
* Have **bounded scope + low regression risk**
* Provide **clear, practical benefit** (not theoretical)
* Are **easy to adopt** (low cognitive overhead)

Exclude:

* Trivial syntax/style tweaks
* Naming or formatting preferences
* Large refactors with marginal gain
* Abstraction for elegance alone
* Over-decomposition increasing indirection
* Vague or non-structural observations

---

### 3. Review Focus (high-value only)

Evaluate:

1. Deduplicable logic
2. Excessive nesting → flattening opportunities
3. Redundant state, traversal, or processing
4. Structures obscuring core flow
5. Patterns increasing long-term maintenance cost

Ignore unrelated topics.

---

### 4. Output Selection Criteria

Keep only items that:

* Reduce duplication
* Lower cognitive / structural complexity
* Remove redundant processing or state
* Make core logic more direct, stable, maintainable

Ignore:

* Minor rewrites with negligible gain
* Micro-optimizations
* Naming / formatting tweaks
* Non-impactful local issues
* Redundant points

---

### 5. Output Format

#### (1) Likely Refactor Objective

One sentence, concise.

#### (2) Actionable Improvements

Format: **Issue → Cause**
Constraints:

* Sorted by impact
* ≤5 items (prefer ≤3)
* Each maps to a concrete structure/pattern
* No redundancy
* No large code rewrites unless essential

#### (3) Conclusion

If no high-value, high-acceptance items:
**No significant optimizations identified**

---

### 6. Stop Condition

Stop once high-value items are exhausted.
Do not include low-impact or stylistic refinements.
