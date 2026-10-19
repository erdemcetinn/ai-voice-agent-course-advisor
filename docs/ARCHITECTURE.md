# Architecture

Design notes for the AI voice agent. For the overview, see the [README](../README.md).

1. [Request lifecycle](#1-request-lifecycle)
2. [Amazon Connect layer](#2-amazon-connect-layer)
3. [AgentCore Gateway](#3-agentcore-gateway)
4. [Tools Lambda](#4-tools-lambda)
5. [Rules engine](#5-rules-engine)
6. [Retrieval](#6-retrieval)
7. [Data model](#7-data-model)
8. [Security model](#8-security-model)
9. [Developer harness and evaluation](#9-developer-harness-and-evaluation)
10. [Design decisions](#10-design-decisions)

---

## 1. Request lifecycle

```text
Student: "Can I take ITC 6680 next semester?"

Contact flow   -> opens an AI agent session for the contact (Connect assistant block)
Lex V2 bot     -> speech to text, hands the turn to the AI agent (AMAZON.QInConnectIntent)
AI agent       -> Claude Haiku 4.5 decides: call plan_next_semester(course_code = "ITC 6680")
Gateway        -> validates the Connect JWT, adds the pinned student_id, invokes Lambda
Lambda         -> loads the student from DynamoDB and the catalog from S3, runs the rules engine
               -> { eligible_now: false, missing_prerequisites: "ITC 6620", counts_toward: ["restricted elective"] }
AI agent       -> "No, you're not eligible yet. You need I T C sixty-six twenty first..."
Lex V2 bot     -> text to speech
```

The model never sees the tool code, only the tool definitions, and it never computes eligibility itself.

## 2. Amazon Connect layer

**Contact flow** (`connect/contact-flow.json`)

| Block | Purpose |
|---|---|
| Set logging behavior | Flow logs to CloudWatch |
| Set recording and analytics behavior | Real-time conversational analytics, required for AI agents on voice |
| Set voice | English (US), generative voice |
| Connect assistant | Associates the contact with the AI agents domain and opens the agent session |
| Get customer input | Invokes the Lex V2 bot with the AI agent intent |
| Disconnect | Ends the contact when the agent returns control (`Complete` or `Escalate`) |

**Bot.** A Lex V2 bot created in Connect with the `AMAZON.QInConnectIntent` enabled and the agentic voice speech model (advanced speech recognition, configurable end-of-turn threshold and timeout).

**AI agent.** An orchestration agent derived from the system self-service voice orchestrator and set as the instance's default self-service orchestrator. Its tools are the three MCP tools from the Gateway plus the built-in `Complete` and `Escalate` return-to-control tools.

**Prompt** (`connect/orchestration-prompt.yaml`). The system voice orchestration prompt with a course-advisor section on top: scope, which tool answers which question, "lead with the yes or no conclusion", how to say course codes aloud, and privacy rules. The base prompt contributes the voice output rules and the `<message>` tag contract that Connect uses to decide what is spoken.

**Voice-first output.** Every answer is written to be read aloud: no markdown, no lists, and course codes spelled as letters and digits ("I T C six six eight zero") so text to speech pronounces them correctly.

## 3. AgentCore Gateway

The Gateway is the bridge between Connect, which speaks the Model Context Protocol, and the Lambda function, which does not.

| Setting | Value |
|---|---|
| Protocol | MCP, including version `2025-03-26` (the version Connect uses) |
| Inbound auth | Custom JWT authorizer with the Connect instance discovery URL (`https://<instance>.my.connect.aws/.well-known/openid-configuration`) |
| Allowed audience | The Gateway ID (Connect puts it in the token's `aud` claim) |
| Allowed clients | Not set |
| Target | Lambda, inline tool schemas from `connect/gateway-tools.json` |
| Outbound auth | Gateway IAM role, allowed only `lambda:InvokeFunction` on the tools function |
| Observability | Application logs delivered to CloudWatch Logs |

Tools appear in Connect with the target as a prefix, for example `advisor_tools___get_transcript`. `scripts/setup_gateway.py` creates or updates the Gateway and target idempotently.

## 4. Tools Lambda

One function, `course-advisor-tools`, serves all three tools.

**Event shape.** The Gateway passes the tool arguments as the event (`{"query": "ITC 6680"}`) and the tool name in `context.client_context.custom["bedrockAgentCoreToolName"]` as `<target>___<tool>`. The handler strips the prefix, removes `student_id` from the arguments, and dispatches through the same `run_tool` used by the terminal agent. A manual event shape (`{"tool": ..., "input": {...}, "student_id": ...}`) is accepted for direct testing.

**Data access.** `src/data.py` reads the catalog and the vector index from S3 into `/tmp` once per container; `load_student` reads DynamoDB when `STUDENTS_TABLE` is set. Only a cold start pays for the downloads.

**Errors.** Tool failures return `{"ok": false, "error": ...}` instead of raising, so the agent can recover gracefully in conversation.

**Packaging.** `scripts/package_lambda.py` builds a zip with the source and a Linux build of NumPy compatible with the Python 3.11 runtime. boto3 comes from the runtime.

## 5. Rules engine

`src/tools/planner.py` (`plan_next_semester`) answers three questions deterministically.

1. **Can the student take this course now?** Prerequisite trees are evaluated against completed courses. Courses marked "may be taken concurrently" are reported as eligible together with their co-requisite.
2. **Does it count toward the degree?** Completed courses are allocated to requirements in order: core, concentration required courses, choice groups, restricted electives, and free electives for the electives option. A course is reported as counting only if it fills a requirement that is still open.
3. **What is left?** Missing core and concentration courses, open choice-group credits and elective credits, and the total credits remaining.

Credits remaining are computed from open requirements, not from "34 minus credits taken", so a course that fills nothing never moves the student closer to graduation. Without a course code the engine returns the full plan: everything still needed, the courses the student can take now that count, and needed courses still blocked by prerequisites.

## 6. Retrieval

**Index.** `scripts/build_index.py` turns the catalog into 76 chunks along natural boundaries: one overview chunk per course, one prerequisite chunk per course that has prerequisites, and program chunks for general rules, required courses, each concentration and restricted electives. Each chunk is embedded with Titan Text Embeddings V2 (1024 dimensions, normalized) and stored as `index.npy` with `chunks.json` row-aligned.

**Search.** `search_catalog` resolves course codes (`ITC 6680`, `itc6680`, `ALY-6145`) with an exact lookup that also reports the course's role in the program. Other queries are embedded with the same model and ranked by dot product, returning the top five chunks with scores. The tool definition asks the model to write search phrases in English, which matches the catalog's language and scores higher.

**Why an in-memory index.** Seventy-six vectors rank in well under a millisecond with one matrix product. A managed vector store would add cost and moving parts without improving results at this scale.

## 7. Data model

**`data/catalog.json`**
- `courses`: 47 courses with title, credits (fixed or ranged), description, the original prerequisite text and the parsed tree.
- `program`: total credits (34), minimum GPA (3.0), required courses, six concentrations plus the electives option (required courses, choice groups, restricted elective credits, free elective credits), restricted electives, and documented special cases.

Prerequisite text is parsed with an operator precedence that matches the catalog: `;` binds more loosely than `or`, so `A ; B or C` means `A and (B or C)`. A cycle check runs over the prerequisite graph.

**`data/students.json`** holds synthetic students at different stages of the program, each validated against the catalog: courses exist, prerequisites were completed in an earlier term, no course repeats. The same records are loaded into DynamoDB with `scripts/load_students.py`.

## 8. Security model

- **Identity is bound outside the model.** Tools that read a student's record take `student_id`, which Connect pins through the tool's input override; the model cannot choose or change it.
- **No secrets in responses.** `get_transcript` never returns the PIN.
- **Least privilege.** Gateway role: invoke one Lambda. Lambda role: read one S3 bucket, `GetItem` on one table, invoke one embedding model. AI agent security profile: three tools.
- **Authenticated tool calls.** The Gateway accepts only JWTs issued by the Connect instance and addressed to this Gateway.
- **Scope control.** The prompt restricts the agent to course planning, and prompt-injection attempts are covered by the evaluation suite.

## 9. Developer harness and evaluation

**Terminal agent.** `src/cli.py` runs the same tools with a tool loop on the Bedrock Converse API (`src/agent/loop.py`): bounded turns, tool errors returned to the model, every tool call printed with its input and latency.

**Evaluation suite.** `evals/` contains scripted conversations across prerequisites, degree progress, catalog facts, out-of-scope requests, unknown information and privacy. `evals/run_evals.py` asks each question several times in fresh conversations; `evals/judge.py` scores answers with a stronger model and checks privacy leaks in code before any model is consulted.

**Tests.** 130 pytest tests cover parsing, the rules engine, retrieval, the tool loop, the Lambda handler and the data layer, without calling AWS.

## 10. Design decisions

| Decision | Reasoning |
|---|---|
| Deterministic rules engine instead of LLM reasoning | Eligibility answers must be consistent and auditable; the model explains, the code decides |
| Tools over a Connect knowledge base integration | A knowledge base retrieves text but cannot evaluate prerequisite trees or credit rules; tools also run unchanged in the terminal harness |
| AgentCore Gateway instead of a custom MCP server | The Gateway turns a Lambda into MCP tools with managed auth and logging |
| One Lambda for three tools | One package and one deployment; the tool code does not depend on it, so splitting later is cheap |
| Claude Haiku 4.5 | Fast responses matter on a phone call, and the heavy lifting is done by the rules engine |
| In-memory vector index | Faster and simpler than a vector database for a corpus of this size |
