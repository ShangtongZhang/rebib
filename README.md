# Rebib
TLDR: This script retrieves information from DBLP to update your BibTex files.

```python --bibfile xxx.bib```

1. It first parses the bib entries in `xxx.bib`.
1. For each entry, it queries DBLP using the title and the first author to retrieve the accurate bibliographical
information. 
    1. If there is only one match, that's it!
    1. If there is no match, skip it.   
    1. If there are two matches, one is arXiv and the other is non-arXiv, it chooses the non-arXiv one.
    1. Otherwise, it lists two most relevant results and ask you to choose one with your keyboard. You can pass `--interactive=False` to just skip this.
1. The updated entries are stored in `xxx_updated.bib` and the skipped ones are stored in `xxx_untouched.bib`.

Use it like a pro: 
* Change `desired` to decide what fields you want to keep in the updated entries.
* Change `query` to decide what you want to send to DBLP.
* Change `num_workers` to decide parallelization (don't be too greedy, you will be banned by DBLP!).
