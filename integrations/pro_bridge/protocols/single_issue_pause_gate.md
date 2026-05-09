# Single issue pause gate

When a real trust defect appears in Pro integration, automation, prompt integrity, capture, or response absorption, pause before the next Pro send.

Pause triggers:

- browser target lock is ambiguous
- prompt hash does not match the visible input
- response capture is incomplete
- response schema is invalid
- source ref is missing for formal review
- local state and Pro session state disagree
- a memory/rule change would rely only on Pro advice

Resume only after the defect is recorded, routed, and the local gate marks it resolved or explicitly deferred.
