# Journal process-death write boundaries (educational)

Run `python3 -m unittest discover -s tests -p 'test_journal_write_crash.py' -v`
on a POSIX host. The tests execute the real `CommandJournal` implementation
in independently spawned processes and inject `os._exit(73)` immediately
after an actual OS write. No AWS infrastructure is used.

- **Partial write:** a process dies after writing half of sequence 2. A new
  instance rejects the incomplete trailing record and does not repair or
  truncate it. Previously committed bytes remain unchanged.
- **Complete write, before fsync:** the process dies after writing all bytes
  for sequence 2 but before calling `fsync`. Reopening can observe a valid
  record. An identical retry is recognized as already present; a different
  payload for the same sequence is rejected. This **does not establish that
  the record survived a power failure**, or that the caller received an
  acknowledgement.

A successful parse is not proof of durable or quorum commitment. After an
ambiguous outcome, the application must reconcile the original command ID
and authoritative commit state before accepting further order operations.
Never automatically truncate a torn record or resubmit an ambiguous order
under a new sequence. Operator-led recovery is required.

This is deterministic process-death fault injection, **not** a filesystem
power-cut test, replicated journal, transaction, distributed fencing, or
split-brain prevention. The journal is not atomically integrated with matching
or ledger settlement and remains unsuitable for production trading.
