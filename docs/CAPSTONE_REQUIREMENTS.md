# Group Project 1: Multi Agent AI System

This file records the requirements from the Canvas assignment PDF so the project
requirements remain available to contributors and AI assistants working in this
repository.

## Source and deadline

- Source: `Group Project 1_ Multi Agent AI System.pdf`, downloaded from Canvas.
- Assignment value: 30 points.
- Due: Monday, September 28, 2026 at 11:59 PM.
- Submission attempts: unlimited.
- The Canvas assignment and course-provided files remain authoritative if this
  summary and Canvas ever differ.

## Goal

Build a two-agent AI system that combines:

- Agent-to-Agent (A2A) communication
- Retrieval-Augmented Generation (RAG)
- Browser automation with Playwright

The required end-to-end flow is:

```text
User Request
  -> Requester Agent
  -> Specialist Agent
  -> RAG
  -> Specialist Response
  -> Requester Agent
  -> Playwright
  -> Verification
```

The Specialist Agent's answer must directly influence at least one action in
the web application. Displaying the RAG answer without using it in the browser
workflow does not satisfy the integration requirement.

## Required components

### 1. Requester Agent

The Requester Agent coordinates the complete workflow. It must:

1. Receive a user request.
2. Determine what information it needs from the Specialist Agent.
3. Create a task for the Specialist Agent.
4. Submit the task through the A2A-style interface.
5. Receive an immediate acknowledgment containing a unique task ID.
6. Poll for task status and the eventual result.
7. Use the Specialist Agent's response to decide what to enter in the web app.
8. Use Playwright to complete the browser interaction.
9. Verify that the expected result occurred.

A rule-based coordinator is acceptable. The Requester Agent does not have to be
a fully autonomous LLM agent.

### 2. Specialist Agent

The Specialist Agent must:

1. Receive a task from the Requester Agent.
2. Search the provided knowledge base.
3. Retrieve relevant documents or passages.
4. Provide the retrieved information to an LLM.
5. Generate a response grounded in the retrieved information.
6. Return the result to the Requester Agent.

It must use RAG; asking an LLM to answer only from its own knowledge is not
sufficient.

### 3. A2A-style communication

The communication layer must include:

- A unique task ID
- A task-submission request
- An immediate acknowledgment
- The statuses `submitted`, `working`, `completed`, and `failed`
- A way to check a task's status
- A way to retrieve the completed result

Simple HTTP requests and JSON are acceptable. A specialized A2A SDK is not
required.

A representative interaction is:

```text
Requester -> Specialist: submit task
Specialist -> Requester: task_id + submitted status
Requester -> Specialist: get task by ID
Specialist -> Requester: working status
Requester -> Specialist: get task by ID
Specialist -> Requester: completed status + result
```

### 4. RAG pipeline

The RAG implementation must:

1. Load the documents.
2. Split them into chunks.
3. Create embeddings.
4. Store embeddings in a vector store.
5. Retrieve relevant chunks for a question.
6. Pass the retrieved information to an LLM.
7. Return an answer based on the retrieved information.

The response must contain enough information to identify the source material
used.

The system must implement and document at least one RAG technique beyond the
foundational techniques numbered 1-6 in the linked `rag_techniques` repository.
The assignment permits the design decision to affect any stage of the RAG
pipeline. The documentation must briefly explain the chosen technique.

Reference supplied by the assignment:
[NirDiamant/rag_techniques](https://github.com/NirDiamant/rag_techniques).

### 5. RAG-to-browser integration

The Specialist Agent's output must control what the Requester Agent enters in
the course-provided application. For the supplied support-ticket scenario, the
Specialist can return a category and resolution, and Playwright can use those
values for the form's issue category and resolution notes.

### 6. Playwright automation

One straightforward browser workflow is sufficient. It must:

1. Open the provided application.
2. Locate the required form fields.
3. Enter information obtained from the Specialist Agent.
4. Submit the form.
5. Verify that the expected result appears.

### 7. Timeout and failure handling

The Requester Agent must stop polling after a defined timeout and display an
appropriate message when a task fails or times out.

The project documentation must explain what happens when:

- The Specialist Agent returns `failed`.
- Retrieval produces no useful knowledge-base information.
- Other failure cases identified by the team occur.

## Required submission

### Source code

Submit source code for:

- Requester Agent
- Specialist Agent
- A2A communication
- RAG pipeline
- Playwright workflow
- Timeout and failure handling

### Knowledge base

Use the course-provided documents. If the team adds documents, keep the total
knowledge base small and focused.

### PDF report

The report must include:

- A brief system description
- An architecture/workflow diagram
- An explanation of the A2A protocol
- An explanation of the RAG pipeline and advanced technique(s)
- An explanation of the Playwright workflow
- A brief reflection covering what worked, what did not, and possible
  improvements

The rubric additionally expects the reflection to discuss limitations,
challenges, RAG effectiveness, agent communication, and potential improvements.

### Video demonstration

The video must show:

- At least one successful end-to-end example
- At least one failure or timeout example

Do not include API keys in the submission.

## Rubric

| Criterion | Points |
| --- | ---: |
| Requester Agent | 3 |
| Specialist Agent and RAG | 3 |
| A2A-style communication | 3 |
| Playwright automation | 3 |
| End-to-end integration | 2 |
| Advanced RAG technique | 2 |
| Error handling | 2 |
| Code quality and execution | 1 |
| PDF report | 2 |
| Video demonstration | 2 |
| Reflection | 2 |
| Participation / team feedback | 5 |
| **Total** | **30** |

## Completion checklist

- [ ] A user request starts the workflow.
- [ ] The Requester submits a Specialist task and immediately receives a unique
      task ID with `submitted` status.
- [ ] Polling visibly exercises the required task states.
- [ ] The Specialist loads and chunks the provided knowledge base.
- [ ] The Specialist creates embeddings and uses a vector store.
- [ ] Retrieved passages are supplied to the LLM.
- [ ] The answer is grounded and identifies its sources.
- [ ] At least one beyond-foundational RAG technique is implemented and
      documented.
- [ ] Specialist output supplies values used by Playwright.
- [ ] Playwright opens, fills, and submits the provided application.
- [ ] Playwright verifies the expected result.
- [ ] `failed`, timeout, and no-useful-retrieval paths are handled and documented.
- [ ] At least one successful end-to-end scenario is tested and ready for the
      video.
- [ ] At least one failure or timeout scenario is tested and ready for the video.
- [ ] The PDF report contains every required section and an architecture diagram.
- [ ] Secrets and API keys are excluded from source control and submissions.
- [ ] Each team member completes the participation/team-feedback requirement.

## Optional extensions

Only pursue these after the required workflow works:

- Additional focused knowledge-base documents
- Passage-level citations
- Structured JSON responses from the Specialist Agent
- Conversation history
- Multiple domain-specific Specialist Agents
- Additional task states
- Retries after agent failures
- A second browser workflow
- Alternative embedding models or retrieval strategies
- An LLM-driven Requester Agent
- RAG quality evaluation

## Assignment-provided references

- [A2A protocol documentation](https://a2a-protocol.org/en/docs)
- [A2A protocol specification](https://a2a-protocol.org/v1.0.0/specification/)
- [A2A Python tutorial](https://a2a-protocol.org/latest/tutorials/python/)
- [A2A GitHub repository](https://github.com/a2aproject/A2A)
- [Playwright Python documentation](https://playwright.dev/python/docs/intro)
- [Playwright test-writing guide](https://playwright.dev/python/docs/writing-tests)
- [Playwright locators](https://playwright.dev/python/docs/locators)
- [Playwright assertions](https://playwright.dev/python/docs/test-assertions)
- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain multi-agent documentation](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [Google Agent Development Kit](https://google.github.io/adk-docs/)

## Repository snapshot when this context was added

The repository already contains:

- A course-style mock support application in `mock_support_app/`
- A small support knowledge base in `knowledge_base/`
- Five categorized example requests in `test_cases.json`
- Pinned dependencies for FastAPI, LangChain, Groq, FAISS, BM25,
  sentence-transformers, Playwright, and testing
- Environment setup instructions and a safe `.env.example`

The Requester Agent, Specialist Agent, A2A service, RAG pipeline, Playwright
workflow, and their tests still need to be implemented.
