# Q&A knowledge sources

Put every presentation knowledge file in this folder. The Q&A index reads
**only** these files plus the loaded PowerPoint deck and `data/script.xlsx`.

Supported without additional software:

- `.txt`
- `.md`
- `.csv`
- `.json`
- `.xlsx` / `.xlsm`

Fact cards (topic, keywords, approved answers, optional slide jump) belong in
`knowledge.xlsx` in this folder. Longer reference material can sit beside it.

Files named `README*` are skipped. Nested folders are included.

Changing or deleting a file here rebuilds the index the next time the deck is
loaded or **Reindex Q&A** is selected. Vectors in Qdrant that no longer match
this folder are deleted at that time.

Keep source material factual. Retrieved text is treated as untrusted reference
data and cannot directly execute PowerPoint actions.
