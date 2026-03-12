# Deferred Items - Phase 01 Prerequisites

## Missing PDFs (4 of 5)

The following PDFs were not found anywhere on the machine during execution:
1. `programmes.pdf` -- Programme details, pricing, duration
2. `faqs.pdf` -- Common questions and answers
3. `payment-details.pdf` -- Bank transfer instructions
4. `objection-handling.pdf` -- Objection response scripts

Only `conversation-sequence.pdf` was found in Downloads and copied to `knowledge-base/`.

**Action required:** User needs to create or locate these 4 PDFs and place them in `knowledge-base/`. Then re-run `python scripts/validate_pdfs.py` to validate.

**Context from CONTEXT.md:** "All 5 PDFs already exist as .pdf files on this machine, ready to copy into knowledge-base/" -- this was the user's claim during discussion, but only 1 was found during execution.
