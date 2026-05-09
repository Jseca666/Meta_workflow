# Meta_workflow Vision

Meta_workflow is a workflow-building workflow: it guides arbitrary projects from unclear goals to explicit business workflows, executable plans, validation gates, and durable memory.

## Target Users

- A project owner who needs business workflows designed from messy goals.
- Codex or another coding agent implementing and maintaining those workflows.
- External reviewers such as Pro who can critique architecture, risks, and plans.

## Engine Shape

Meta_workflow should evolve into a workflow engine with these subsystems:

- Intake: capture project goals, constraints, stakeholders, and success criteria.
- Decomposer: break goals into workflow phases, tasks, artifacts, and gates.
- Composer: propose next workflow actions and artifact updates.
- Monitor: enforce policy, evidence, safety, validation, and scope constraints.
- Predictor: estimate consequences before changes are executed.
- Evaluator: score alternatives by quality, risk, cost, reversibility, and business fit.
- Orchestrator: manage state transitions, pause/resume, retry, escalation, and completion.
- Memory and Recall: retrieve prior knowledge and write back verified durable facts.
- External Expert Bridge: request and absorb Pro feedback through controlled protocols.

## V1 Success Criteria

- A project goal can be converted into a structured workflow spec.
- Every workflow step has owner, evidence, validation, and acceptance criteria.
- External Pro review can be requested through GitHub source refs.
- Memory writeback is explicit and separated from raw conversation.
- The engine can resume from recorded state rather than relying on chat context.

## Roadmap

- Phase 0: establish repository contracts, Pro Bridge, methodology docs, and source-ref review loop.
- Phase 1: define workflow spec schemas, event log, memory records, and recall packets.
- Phase 2: build a runnable local engine for planning, gate checks, execution records, and resume.
- Phase 3: add evaluation loops, Pro review ingestion, and self-improvement workflows.
- Phase 4: add UI/API surfaces after the file and CLI protocol stabilizes.
