---
name: zt
description: Start or continue ZepTeach teaching when the learner invokes /zt.
---

# ZepTeach short entry

This is the short entry for the ZepTeach plugin. Resolve this skill's real
directory, then read the sibling `../zepteach/SKILL.md` completely and follow
its routing and teaching rules. The main skill holds the method; do not
duplicate it here.

Treat text after `/zt` as the learner's request. Run the main skill's
`scripts/route.py next --said "<request>"`, using the configured learner data
root. With no text, continue from the stored state. A nonzero exit is a
refusal with a reason; do not work around it.
