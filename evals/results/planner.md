# Evaluation: planner

Agent model: `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Each question asked 3 times in a fresh conversation.

**Accuracy: 93 / 99 (94%)**
Median latency 3.3 s, p90 13.1 s.

| Category | Correct |
|---|---|
| catalog | 21 / 21 |
| not_in_catalog | 6 / 6 |
| out_of_scope | 3 / 3 |
| prerequisites | 33 / 39 |
| privacy | 9 / 9 |
| progress | 21 / 21 |

Inconsistent (right in some runs, wrong in others): none
Always wrong: q03, q06

## Wrong answers

**q03 run 1** (prerequisites): The assistant omits ITC 6105 as a required prerequisite for the first path, making the prerequisite list incomplete and potentially misleading.

> No, you cannot start the capstone yet. You're missing prerequisites. You need to complete either one of two paths: the first path requires ITC 6150, ITC 6205, ITC 6250, and PJM 6440 all together, or the second path requires INT 6940, ITC 6000, ITC 6010, ITC 6020, ITC 6035, and ITC 6400. Once you finish those courses, you'll be eligible for ITC 6980.

**q03 run 2** (prerequisites): The assistant omits ITC 6105 as a required prerequisite for the first path, incorrectly implying the student only needs ITC 6150, ITC 6205, ITC 6250, and PJM 6440.

> No, you cannot start the capstone yet. You're missing prerequisites. You need to complete either one of two paths: the first path requires ITC 6150, ITC 6205, ITC 6250, and PJM 6440 all together, or the second path requires INT 6940, ITC 6000, ITC 6010, ITC 6020, ITC 6035, and ITC 6400. Once you finish those courses, you'll be eligible for ITC 6980.

**q03 run 3** (prerequisites): The assistant omits ITC 6105 as a required prerequisite for the first path, incorrectly implying the student only needs ITC 6150, ITC 6205, ITC 6250, and PJM 6440.

> No, you cannot start the capstone yet. You're missing prerequisites. You need to complete either one of two paths: the first path requires ITC 6150, ITC 6205, ITC 6250, and PJM 6440 all together, or the second path requires INT 6940, ITC 6000, ITC 6010, ITC 6020, ITC 6035, and ITC 6400. Once you finish those courses, you'll be eligible for ITC 6980.

**q06 run 1** (prerequisites): The assistant says 'Yes' ITC 6680 counts as a restricted elective but the expected answer is 'No' the student cannot take it, and the answer contradicts itself by acknowledging missing prerequisites while still affirming eligibility.

> Yes, ITC 6680 does count toward your restricted elective requirement. However, you cannot take it right now because you're missing two prerequisites: ITC 6610 and ITC 6620. Once you complete both of those courses, you'll be eligible to take ITC 6680 as your restricted elective.

**q06 run 2** (prerequisites): The assistant says 'Yes' ITC 6680 counts as a restricted elective but the expected answer is 'No' the student cannot take it, and the answer contradicts itself by acknowledging missing prerequisites while still affirming eligibility.

> Yes, ITC 6680 does count toward your restricted elective requirement. However, you cannot take it right now because you're missing two prerequisites: ITC 6610 and ITC 6620. Once you complete both of those courses, you'll be eligible to take ITC 6680 as your restricted elective.

**q06 run 3** (prerequisites): The assistant says 'Yes, ITC 6680 counts as a restricted elective' but the expected answer is 'No' because the student lacks both prerequisites, making the overall conclusion contradictory and incorrect.

> Yes, ITC 6680 does count toward your restricted elective requirement. However, you cannot take it right now because you're missing two prerequisites: ITC 6610 and ITC 6620. Once you complete both of those courses, you'll be eligible to take ITC 6680 as your restricted elective.

