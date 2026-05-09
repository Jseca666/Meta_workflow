# MAP Methodology For Meta_workflow

This note distills the paper `references/papers/s41467-025-63804-5.pdf`, "A brain-inspired agentic architecture to improve planning with LLMs", into working methodology for Meta_workflow.

## Core Lesson

The paper's useful idea is not "use many agents". It is to factor planning into specialized functions that repeatedly coordinate around a goal. Meta_workflow should copy that factorization, then extend it with durable memory and recall.

## Module Mapping

| MAP module | Paper role | Meta_workflow role |
| --- | --- | --- |
| TaskDecomposer | Turns a high-level goal into subgoals | Converts a project/business goal into workflow stages and deliverables |
| Actor | Proposes actions for a state and subgoal | Proposes workflow steps, tool calls, artifacts, or implementation tasks |
| Monitor | Rejects invalid actions and gives feedback | Enforces policy, scope, evidence, safety, validation, and source-ref gates |
| Predictor | Predicts the next state after an action | Simulates likely consequences, dependencies, and downstream state changes |
| Evaluator | Scores predicted states against the goal | Scores quality, risk, cost, reversibility, and business fit |
| Orchestrator | Determines subgoal/final-goal completion | Controls workflow lifecycle, pause/resume, retry, escalation, and completion |

## Meta_workflow Extensions

MAP does not provide a full product-grade workflow engine. Meta_workflow needs additional modules:

- Recall: retrieve prior project facts, workflow patterns, decisions, failures, and reusable playbooks.
- Memory Writer: write only verified durable facts, not raw observations or external advice.
- Consolidator: merge repeated lessons into stable project and methodology memory.
- External Expert Bridge: route Pro feedback as evidence, not as authority.
- Event Log: preserve every meaningful state transition for replay and debugging.

## Design Principles

- Prefer functional modules over persona-style agents.
- Gate proposed actions before execution.
- Keep source-grounded evidence attached to every external review.
- Treat memory writeback as a separate decision, not a side effect of conversation.
- Make state explicit: current goal, subgoal, candidate action, predicted state, score, gate result, and next action.

## Open Questions For Pro

- What is the smallest useful v1 engine surface: CLI, file protocol, API, UI, or all of them?
- Which memory and recall store should be introduced first?
- How much of MAP-style tree search is useful for business workflow construction versus overkill?
- Which gates should be hard blockers in v1?
