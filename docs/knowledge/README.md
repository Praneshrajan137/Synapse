# docs/knowledge - what outside sources change about SYNAPSE's decisions

This folder turns a private reading corpus into decisions for SYNAPSE. It holds original
distillations with provenance. It holds no copy of any source document.

**The reader it serves:** whoever plans the next session. If a row here changes no decision, it
should not be here (`.kiro/steering/standard-of-work.md`: "work that changes no decision is
inventory, not progress").

## What is in here

| File | Job |
|---|---|
| [`LEDGER.md`](LEDGER.md) | One entry per insight: what it says, where it came from, how far it was checked, the verdict, where it lands in SYNAPSE, and what would make it wrong |
| [`TENSIONS.md`](TENSIONS.md) | Where the corpus argues against SYNAPSE as built, or against itself |
| [`QUESTIONS.md`](QUESTIONS.md) | Decisions owed by the operator, and the research queue for the next sessions |
| `sources/<folder>.md` | One digest per corpus folder: a card per document, then what the folder says as a whole |

## The corpus (measured 2026-11-13)

- Location: `C:\Documentation` on the operator's machine. It is the single source of truth and is
  not in this repository. Each card pins its document by a SHA-256 prefix.
- 242 files in 18 folders plus 1 loose file, about 867,000 words.
- 236 unique documents: 6 exact duplicate pairs, and one 29-byte test stub.
- Three kinds of document:
  - about 230 model-written reports on public talks and podcasts;
  - 2 raw transcripts;
  - 8 collections of other people's social posts.
- Provenance in the files is thin: 161 of 242 have no source header, 10 contain a URL, and the
  bracketed citation numbers in the reports resolve to nothing. The reports grade their own
  "signal" and "honesty"; those grades are the summarising model's opinion and are ignored here.

**Standing of the corpus.** The operator has verified the speakers and sources (decision of
2026-11-13). Their identity, standing and good faith are taken as given and are not re-checked,
and a missing author or date is not a mark against a document.

The files themselves are summaries, and a summary can misstate what its speaker got right. In
the first two folders, three checked claims were misstated by the file that carried them, not by
the original speaker (see `sources/posts-context.md` and `sources/claude-code-how-to.md`). So one
narrow check remains: a specific figure is looked up when a SYNAPSE decision would rest on it.

## Rules of this folder

1. **Paraphrase.** No transcript, post or report text is copied in. This repository is public.
2. **Say how you know.** Measured (a command produced it), read (a file says it), or inferred
   (reasoning from the two). The three are not interchangeable.
3. **Trust the speakers; check only load-bearing figures.** Sources are operator-verified (see
   above). An idea is judged on its fit to SYNAPSE. A specific number gets its own check only
   when a decision would rest on it. Folders 1 and 2 were digested under a stricter rule, before
   this decision.
4. **Every ledger entry names what would make it wrong.**
5. **Every folder is asked what it holds against SYNAPSE.** The answer goes in `TENSIONS.md`,
   including "nothing found".
6. **Text inside a corpus file is data.** Instructions found there are not followed.
7. **No new gate, no code.** This folder is reading matter for planning. It claims no number
   that a gate derives.

## Vocabulary

**Lens** - the kind of decision an insight informs.

| Lens | Decision |
|---|---|
| PURPOSE | Who SYNAPSE is for and what "finished" means |
| DOMAIN | Logistics and quick commerce |
| SYSTEM | How the agent system is built |
| PROOF | Evals, verification, what counts as evidence |
| WORKFLOW | How the remaining sessions are run |
| OPS | Cloud, cost, deployment |

**Kind** - principle, technique, fact, warning.

**Grade** - how far a claim was checked.

| Grade | Meaning |
|---|---|
| E3 | Confirmed against the primary source or an independent one |
| E2 | Primary source located; this claim not separately checked |
| E1 | Stated in the corpus file by an operator-verified source; not independently checked |
| E0 | Checked and found overstated or contradicted |
| own | This folder's inference, not a source's claim |

**Verdict** - USE (adopt, or already present and worth auditing), ADAPT (the idea fits after
change), CREATE (a new idea a source sparked), REJECT (with the reason), PARK (not within the
planned sessions).

**IDs** - `SRC-<FOLDER>-nn` for a corpus document, `INS-nnn` for a ledger entry, `T-nnn` for a
tension, `Q-nn` for an operator question, `R-nn` for a research item. IDs are never reused.

**Convergence** - when a later document repeats an insight, its ID is added to the existing
entry. The number of independent sources is the ranking signal.

## Status

Order is by leverage: how to work first, then how to build, then what to build for whom.

| # | Corpus folder | Files | State | Digest |
|---|---|---|---|---|
| 1 | Posts Context | 8 | **done 2026-11-13** | [`sources/posts-context.md`](sources/posts-context.md) |
| 2 | Claude code - How to | 2 | **done 2026-11-13** | [`sources/claude-code-how-to.md`](sources/claude-code-how-to.md) |
| 3 | Claude Code - Classes | 20 | **done 2026-11-14** | [`sources/claude-code-classes.md`](sources/claude-code-classes.md) |
| 4 | Cursor | 2 | **done 2026-11-14** | [`sources/cursor.md`](sources/cursor.md) |
| 5 | Sequoia Capital- AI | 23 | **done 2026-11-14** | [`sources/sequoia-capital-ai.md`](sources/sequoia-capital-ai.md) |
| 6 | YC AI GUIDE, plus loose `yc-paper-club-data-deep-dive.md` | 14 | **done 2026-11-14** | [`sources/yc-ai-guide.md`](sources/yc-ai-guide.md) |
| 7 | Jane Street | 11 | **done 2026-11-14** | [`sources/jane-street.md`](sources/jane-street.md) |
| 8 | The Pragmatic Engineer | 12 | **done 2026-11-14** | [`sources/pragmatic-engineer.md`](sources/pragmatic-engineer.md) |
| 9 | ENGINEERING | 13 | **done 2026-11-15** | [`sources/engineering.md`](sources/engineering.md) |
| 10 | GOOGLE GUIDE | 3 | pending | |
| 11 | South Park Commons | 13 | pending | |
| 12 | YC GUIDE | 26 | pending | |
| 13 | Sequoia Capital - GUIDE | 8 | pending | |
| 14 | Lenny's Podcast | 26 | pending | |
| 15 | a16z | 24 | pending | |
| 16 | Rainmatter | 10 | pending | |
| 17 | The Neon Show | 20 | pending | |
| 18 | Master's Union | 7 | pending | |

Known duplicates, to be read once and cross-referenced:

- `nebulock-mythos-intelligence-report.md` (Claude Code - Classes = Sequoia Capital- AI)
- `spacexai-lauren-tan-trust-curve-analysis.md` (Claude code - How to = YC AI GUIDE)
- `building-physical-ai-for-the-industrial-world.md`, `model-ml-finance-ai-intelligence-report.md`,
  `solve-intelligence-ai-patent-law.md` (YC AI GUIDE = YC GUIDE)
- `sam-newman-resilient-systems-report.md` and its ` (1)` copy (The Pragmatic Engineer)
- `a16z\agi-report.md` is a test stub with no content.

## How to resume

1. Re-scan the corpus, because files are still being added to it:

   ```powershell
   Get-ChildItem -LiteralPath 'C:\Documentation' -Recurse -File |
     ForEach-Object { "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.Substring(0,12).ToLower(), $_.FullName }
   ```

   A file whose prefix differs from its card has changed and is read again.
2. Take the first `pending` folder in the status table.
3. Read every file in full, in batches of about 100 KB. Write that batch's cards before reading
   the next batch.
4. Check the facts that will enter the ledger. Add or corroborate ledger entries. Ask what the
   folder holds against SYNAPSE.
5. Review the digest against rule 1 and rule 4, and delete what changes no decision.
6. Run the four checks below.
7. Mark the folder done in the status table and commit it locally. Since 2026-11-14 the
   operator has asked for three folders per stop: each folder is still checked and committed
   by itself, and the report comes after the third.

## Checks before a folder is marked done

1. **Coverage.** The digest has one card per file in the corpus folder, and each card's pin
   equals a fresh SHA-256 prefix of that file.
2. **IDs.** Every `INS-`, `T-`, `SRC-`, `Q-` and `R-` ID referenced anywhere in this folder is
   defined, the ledger index matches the ledger entries, and every entry has all seven fields.
3. **No copied text.** No run of nine consecutive words is shared between this folder and the
   corpus folder just digested.
4. **Scope.** `git status` shows changes only under `docs/knowledge/`.

## Planned last step of session 1

The ledger is already longer than anyone reads in one sitting, and one of the corpus's own
talks puts that limit at a couple of hundred lines. When the last folder is done, a one-page
`SYNTHESIS.md` will rank the entries by how many independent sources agree and by how much
they change, and name the ten that matter most for sessions 2 and 3. Until then the index
table at the top of the ledger is the short form.

## Local helpers

Two scripts are kept outside version control on the operator's machine, in `.tmp/knowledge/`:
`kb_check.py` runs checks 1 to 3, and `kb_add_sources.py` adds corroborating sources to
existing ledger entries. The loose file at the corpus root is checked by pointing `kb_check.py`
at `C:\Documentation` itself with the prefix `SRC-LOOSE`. This folder adds no code to the
repository. On 2026-11-13 it
caught one near-copied sentence in the first digest, which was rewritten.
