# Ingestion and chunking

## Loaders (`backend/ingest.py`)
| Type | Becomes | Why |
|---|---|---|
| `.md`, `.txt` | one Doc | Headings are kept for section-aware chunking |
| `.pdf` | one Doc per page (`meta.page`) | Citations can point at a page |
| `.csv`, `.json` (list of objects) | one Doc of records, each line `column: value; column: value` | A row stays together, so values aren't separated from their column names |
| `.html` | text with scripts and styles removed | Markup isn't indexed |

Every Doc carries `source` (its path relative to the data folder), `folder` (the top-level folder, used for authorization) and `type`.

`load_corpus()` returns the docs plus the list of skipped files. Show the skipped list to the owner instead of hiding it.

## Chunking (`chunk_docs`)
- **Markdown:** the text is split on headings, and each chunk keeps its heading path (for example `Returns › Kayaks`; in the code the separator is a greater-than sign) as its first line. A chunk then still says what it's about when it's retrieved on its own.
- **Records:** rows are packed together up to `CHUNK_SIZE`, never split in the middle of a row.
- **Long text:** split on paragraphs, then sentences, and packed to `CHUNK_SIZE` characters with `CHUNK_OVERLAP` overlap.
- Chunk ids look like `source::n`, so they stay stable across runs as long as the file is unchanged. Eval matches expected sources against these ids.

## Tuning
| Setting | Default | Raise when | Lower when |
|---|---|---|---|
| `CHUNK_SIZE` | 1200 chars | answers need context spread across paragraphs | eval shows the right doc is retrieved but the answer passage is diluted |
| `CHUNK_OVERLAP` | 150 | facts get cut at boundaries | the index has too many near-duplicate chunks |

Change one setting at a time, then re-ingest and run eval. The template's regression test shows that a bad chunk size (60/40) drops `citation_hit` from 0.714 to 0.571. That is the kind of drop the baseline catches.

## Tests to keep or add
- Each loader on a tiny fixture: the right number of Docs, and the metadata is set.
- A CSV row is never split across chunks.
- Heading paths survive chunking.
- An unsupported file is reported as skipped, not silently dropped.
