# Rollback and stop

Stop the Pro workflow immediately when a gate fails.

Safe rollback actions:

- do not send
- do not count the response
- mark the run blocked
- keep raw evidence for diagnosis
- open a follow-up defect record

Unsafe rollback actions:

- deleting Pro conversations without an explicit local registry match
- overwriting prompt or response evidence
- converting Pro advice directly into memory
- continuing to a second Pro send while a blocking trust defect is unresolved
