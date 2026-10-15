# Architecture

This document explains how the pieces fit together and why each design choice was made.
For the overview, see the [README](../README.md).

1. [Tool use: the LLM asks, our code runs](#1-tool-use-the-llm-asks-our-code-runs)
2. [The tool loop](#2-the-tool-loop)
3. [The phone path: how Connect knows about our tools](#3-the-phone-path-how-connect-knows-about-our-tools)
4. [One Lambda, several tools](#4-one-lambda-several-tools)
5. [Retrieval (RAG)](#5-retrieval-rag)
6. [Why not Bedrock Knowledge Bases](#6-why-not-bedrock-knowledge-bases)
7. [Data model](#7-data-model)
8. [Security boundaries](#8-security-boundaries)
9. [Open questions](#9-open-questions)

---

## 1. Tool use: the LLM asks, our code runs

An LLM cannot execute code or reach a database. It only produces text. Tool use works by giving the model a menu of **tool definitions** (name, description, input schema) and letting it respond with a structured request instead of an answer:

```text
Student:  "Can I take ITC 6680?"

LLM   ->  tool request: get_transcript
Code  ->  runs get_transcript("s001")      -> ITC 6105 (A), ITC 6610 (A-)
LLM   ->  tool request: search_catalog("ITC 6680")
Code  ->  runs the search                  -> prerequisites: ITC 6610 AND ITC 6620
LLM   ->  "Not yet. You still need ITC 6620."
```

The model never sees the tool's code, only its definition. The quality of the description directly affects whether the model picks the right tool.

## 2. The tool loop

In the terminal path, `src/agent/loop.py` (phase 3) sits between the model and the tools:

```text
1. Send the conversation and the tool definitions to Bedrock (Converse API)
2. Look at the response:
     plain text    -> done, show it to the student
     tool request  -> go to 3
3. Run the requested Python function (inject the session's student ID if needed)
4. Append the tool result to the conversation, go back to 2
```

Two guards are part of the design:
- **Turn limit.** If the model keeps requesting tools, the loop stops after a fixed number of turns. No infinite loops, no runaway cost.
- **Errors become messages.** A failing tool does not crash the session. The error goes back to the model, which can tell the student it cannot check right now.

The loop is written by hand on purpose. A managed agent runtime would hide every step; writing it makes the mechanics visible and measurable.

**Retrieval is agentic.** The model decides when to search and what to search for. Greetings and transcript questions trigger no search at all, and the model can search more than once in a single answer.

## 3. The phone path: how Connect knows about our tools

On the phone, Amazon Connect runs the same loop internally. It is a **cascaded** pipeline: speech recognition, then the LLM, then text-to-speech. It is not a speech-to-speech model.

Connect is configured with the same three things the terminal loop uses:

| What | Terminal | Phone |
|---|---|---|
| Instructions (system prompt) | `prompts.py` | AI agent configuration in Connect |
| Tool definitions | Sent by `loop.py` to Bedrock | Discovered from **AgentCore Gateway** |
| Where tools run | Local Python | **AWS Lambda** (same Python code) |

Connect speaks to tools over **MCP**. Lambda does not speak MCP, so AgentCore Gateway sits in between and exposes the Lambda as MCP tools. No custom MCP server is written.

```text
Connect  -> "which tools exist?"  -> Gateway -> tool definitions
Connect  -> call get_transcript   -> Gateway -> Lambda -> result back the same way
```

Prompt and tool definitions are tuned in the terminal first and then carried over to Connect almost unchanged.

## 4. One Lambda, several tools

The three tools share one Lambda that routes on the requested tool name:

```python
def handler(event, context):
    tool = requested_tool_name(event, context)
    if tool == "get_transcript":     return get_transcript(...)
    if tool == "search_catalog":     return search_catalog(...)
    if tool == "plan_next_semester": return plan_next_semester(...)
```

| One Lambda per tool | One Lambda for all tools (chosen) |
|---|---|
| Least privilege per tool (only the transcript tool can read student records) | One package, one deployment, one place to debug |
| Independent deploys and memory settings | Fits three small tools and a single developer |

The tool code does not depend on this choice, so splitting later is cheap.

## 5. Retrieval (RAG)

RAG is a method: **R**etrieve relevant text, **A**ugment the prompt with it, let the model **G**enerate an answer grounded in it.

### Indexing (once, `scripts/build_index.py`)

```text
catalog.json -> 76 chunks -> Titan Text Embeddings V2 -> data/index.npy  (76 x 1024 numbers)
                          \-------------------------> data/chunks.json  (the texts)
```

Chunks follow natural boundaries instead of a fixed size:
- one overview chunk per course (code, title, credits, description)
- one prerequisite chunk per course that has prerequisites
- program chunks: general rules, required courses, each concentration, restricted electives

The two files line up row by row. Row *i* of `index.npy` is the embedding of row *i* of `chunks.json`. The numbers only answer "which rows are closest?"; the texts are what reaches the model.

### Searching (every call, `src/tools/catalog_search.py`, phase 2.3)

```text
query has a course code ("ITC 6680")  -> exact lookup in catalog.json, no embedding
otherwise ("data visualization")      -> embed the query -> compare with every row -> top rows -> texts
```

The text that gets embedded is the model's search query, not the student's raw sentence. The model turns a rambling spoken question into a short, focused query, which improves retrieval.

Embeddings are **normalized** to length 1, so cosine similarity is a single dot product. Both indexing and search go through `src/embeddings.py`; using the same model and settings on both sides is what makes the numbers comparable.

### Why numpy

76 vectors compare in well under a millisecond with one matrix product. A vector database or FAISS adds setup and, for some managed options, an idle cost, with no benefit at this size. If the corpus grows into the thousands, FAISS is the next step.

## 6. Why not Bedrock Knowledge Bases

A Bedrock Knowledge Base is the managed version of section 5: upload documents to S3, pick an embedding model and a vector store, press Sync, then call `retrieve`.

The mechanism is identical. Embeddings are still computed (by AWS instead of our code), and the model still does not search by itself: a tool or an integration calls the Knowledge Base on its behalf.

It was not used here for design reasons:
- **It hides the parts worth understanding.** Chunking, embedding and similarity search all happen out of sight.
- **It needs a vector store.** Some store options bill while idle, which does not fit a small budget.
- **The corpus is tiny.** 76 chunks fit in one numpy file.

The structured catalog (`catalog.json`) would be needed either way. A Knowledge Base only searches text; the planner needs prerequisite trees and credit rules.

## 7. Data model

**`data/catalog.json`**
- `courses`: 47 courses with title, credits, description, original prerequisite text (`prereq_text`) and the parsed tree (`prereq`).
- `program`: total credits (34), minimum GPA (3.0), required courses, six concentrations plus an electives option, restricted electives, and `notes` for special cases that are documented but not computed.

Prerequisite trees use `and` / `or` nodes with course leaves. In the catalog, `;` binds more loosely than `or`, so `A ; B or C` means `A and (B or C)`. A cycle check runs over the prerequisite graph before the data is used.

**`data/students.json`**: three synthetic students at different stages (first term, mid-program, near graduation). Terms are numbered instead of dated, and every record is validated against the catalog: courses exist, prerequisites were completed in an earlier term, no course is taken twice.

The catalog is static and read as a whole, so it lives in a file (S3 in the cloud). Student records change and are read one at a time by key, so they move to DynamoDB in phase 6.

## 8. Security boundaries

- The student ID comes from the session, never from the model. `get_transcript` has no ID parameter in its tool definition; the code injects it.
- `get_transcript` never returns the PIN.
- On the phone, the caller authenticates with ID and PIN in the contact flow before the AI agent starts.
- If the phone path cannot bind the student ID outside the model (see open questions), `get_transcript` stays disabled on the phone and the agent answers catalog questions only. Privacy wins over features.

## 9. Open questions

These are unverified and will be tested in phase 7:
- How AgentCore Gateway passes the requested tool name to a Lambda target.
- Whether Connect's "override input values" can fill a tool parameter from a contact attribute (the authenticated student ID).
