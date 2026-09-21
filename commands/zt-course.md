---
description: Create a course from a goal
---

Read `curriculum-design.md` and `adapter-contract.md`.

Order matters:

1. Ask what they will be able to DO at the end, and where they expect to
   actually use it. Both, and as specifically as they can manage.
2. Write the adapter from that answer. Every target it declares records
   which part of the answer makes it necessary.
3. Lay out concepts, prerequisites and depth targets.
4. Add near-term milestones, not only an end date.
5. `curriculum.py register-concepts` then `curriculum.py validate`.

Then run `/zt-probe` before teaching anything.

Then run `/zepteach:zt-probe` yourself. A course that has not been checked
for what its practice can act on cannot be taught, and the check is gated in
code, so stopping here leaves the learner one command short of anything
happening.
