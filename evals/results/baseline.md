# Evaluation: baseline

Agent model: `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Each question asked 3 times in a fresh conversation.

**Accuracy: 93 / 99 (94%)**
Median latency 4.7 s, p90 12.4 s.

| Category | Correct |
|---|---|
| catalog | 21 / 21 |
| not_in_catalog | 6 / 6 |
| out_of_scope | 3 / 3 |
| prerequisites | 36 / 39 |
| privacy | 9 / 9 |
| progress | 18 / 21 |

Inconsistent (right in some runs, wrong in others): none
Always wrong: q07, q19

## Wrong answers

**q07 run 1** (prerequisites): The assistant says yes and implies the course fits toward graduation, but fails to mention that ALY 6620 would not count toward the remaining graduation requirements.

> Yes, you can take ALY 6620. You have completed ALY 6115 with an A, which satisfies the main prerequisite for Big Data and Cloud Computing. You have 28 credits completed and need 34 to graduate, so you have room for this course.

**q07 run 2** (prerequisites): The assistant says yes and implies the course fits toward graduation, but fails to mention that ALY 6620 would not count toward the remaining graduation requirements.

> Yes, you can take ALY 6620. You have completed ALY 6115 with an A, which satisfies the main prerequisite for Big Data and Cloud Computing. You have 28 credits completed and need 34 to graduate, so you have room for this course.

**q07 run 3** (prerequisites): The assistant says the student can take ALY 6620 and implies it counts toward graduation credits, but fails to mention that ALY 6620 would not count toward graduation requirements since the Analytics choice group is already satisfied by ALY 6610.

> Yes, you can take ALY 6620. You have completed ALY 6115 with an A, which satisfies the main prerequisite for Big Data and Cloud Computing. You have 28 credits completed and need 34 to graduate, so you have room for this course.

**q19 run 1** (progress): The assistant states ITC 6980 is 3 credits when it is actually 4 credits, and misidentifies the remaining requirement as a 3-credit concentration course rather than 2 credits of restricted electives.

> You have completed 28 of 34 credits required to graduate. You're in the Analytics concentration, so you need 6 more credits to finish. You still need to take the Informatics Capstone (ITC 6980, 3 credits) and one more 3-credit course to meet your concentration requirements. Your GPA is 3.68, which exceeds the 3.0 minimum. I'd recommend checking with your academic advisor about which specific elective would best complete your Analytics concentration.

**q19 run 2** (progress): The assistant states ITC 6980 is 3 credits (wrong, it's 4) and doesn't correctly identify the remaining requirement as 2 credits of restricted electives, instead vaguely mentioning a 3-credit concentration course.

> You have completed 28 of 34 credits required to graduate. You're in the Analytics concentration, so you need 6 more credits to finish. You still need to take the Informatics Capstone (ITC 6980, 3 credits) and one more 3-credit course to meet your concentration requirements. Your GPA is 3.68, which exceeds the 3.0 minimum. I'd recommend checking with your academic advisor about which specific elective would best complete your Analytics concentration.

**q19 run 3** (progress): The assistant states ITC 6980 is 3 credits (wrong, it's 4) and doesn't correctly identify the remaining requirement as 2 credits of restricted electives, instead vaguely mentioning a 3-credit concentration course.

> You have completed 28 of 34 credits required to graduate. You're in the Analytics concentration, so you need 6 more credits to finish. You still need to take the Informatics Capstone (ITC 6980, 3 credits) and one more 3-credit course to meet your concentration requirements. Your GPA is 3.68, which exceeds the 3.0 minimum. I'd recommend checking with your academic advisor about which specific elective would best complete your Analytics concentration.

