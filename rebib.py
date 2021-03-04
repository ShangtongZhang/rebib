import pybtex
from pybtex.database.input import bibtex
import bibtex_dblp.dblp_api
import requests
import numpy as np
import multiprocessing as mp
from absl import flags
import sys
import os


flags.DEFINE_string('dir', '/Users/Shangtong/GoogleDrive/Paper/phd_thesis', 'base directory')
flags.DEFINE_string('bibfile', 'ref', 'input file')
flags.DEFINE_integer('num_workers', 5, 'parallelization')
flags.DEFINE_bool('interactive', True, 'manually choose a candidate when there are two candidates')
flags.DEFINE_string('format', 'bibtex', 'format of the file')
flags.FLAGS(sys.argv)
FLAGS = flags.FLAGS


def filter_fields(pub):
    desired = ['title', 'booktitle', 'year', 'journal', 'school']
    return {k: pub.fields[k] for k in desired if k in pub.fields.keys()}


def update_entry_with_pub(entry, pub):
    bytes = requests.get(f'{pub.url}.bib')
    updated_entries = pybtex.database.parse_bytes(bytes.content, bib_format=FLAGS.format)
    assert len(updated_entries.entries) == 1
    for new_key in updated_entries.entries:
        updated_entry = updated_entries.entries[new_key]
    if pub.venue == 'CoRR':
        # hard-coding for arxiv publications
        updated_entry.fields['journal'] = f'arXiv preprint arXiv:{updated_entry.fields["volume"][4:]}'
    updated_entry = pybtex.database.Entry(
        type_=updated_entry.type,
        persons=updated_entry.persons,
        fields=filter_fields(updated_entry)
    )
    if 'editor' in updated_entry.persons.keys():
        del updated_entry.persons['editor']
    updated_entry.key = entry.key
    return updated_entry


def update_entry_wrapper(entry):
    result = None
    for _ in range(5):
        try:
            result = update_entry(entry)
        except:
            continue
    result = result or dict(succeeded=None, failed=entry, info=None, pending=None)
    return result


def pub_to_str(pub):
    authors = ' '.join([author.name['text'] for author in pub.authors])
    return f'{authors} {pub.venue} {pub.title}'


def update_entry(entry):
    author = str(entry.persons['author'][0])
    title = entry.fields['title']
    query = f'{title} {author}'
    result = dict(succeeded=None, failed=None, info=None, pending=None)
    try:
        search_results = bibtex_dblp.dblp_api.search_publication(query, max_search_results=2)
    except:
        result['failed'] = entry
        result['info'] = 'DBLP request error'
        return result
    if search_results.total_matches == 0:
        result['failed'] = entry
    else:
        pubs = [result.publication for result in search_results.results]
        is_arxiv = [pub.venue == 'CoRR' for pub in pubs]
        if len(is_arxiv) == 1:
            # only one match, no other choice
            pub = pubs[0]
        elif np.sum(is_arxiv) == 1:
            # one is arxiv and the other is not, use the non-arxiv one
            pub = pubs[np.argmin(is_arxiv)]
        else:
            result['pending'] = (query, pubs, entry)
            return result
        result['succeeded'] = update_entry_with_pub(entry, pub)

    return result


def rebib():
    parser = bibtex.Parser()
    bib_data = parser.parse_file(os.path.join(FLAGS.dir, f'{FLAGS.bibfile}.bib'))
    entries = [bib_data.entries[key] for key in bib_data.entries]
    if FLAGS.num_workers > 1:
        pool = mp.Pool(processes=FLAGS.num_workers)
        results = pool.map(update_entry_wrapper, entries)
    else:
        results = [update_entry_wrapper(entry) for entry in entries]
    for res in results:
        if res['pending'] is not None:
            query, pubs, entry = res['pending']
            if FLAGS.interactive:
                hint = f'Select a candidate for {query}: \n (0) Skip \n (1) {pub_to_str(pubs[0])} \n (2) {pub_to_str(pubs[1])} \n'
                selected = int(input(hint))
                if not selected:
                    res['failed'] = entry
                else:
                    pub = pubs[selected - 1]
                    res['succeeded'] = update_entry_with_pub(entry, pub)
            else:
                res['failed'] = entry
    updated = []
    untouched = []
    for res in results:
        if res['succeeded'] is not None:
            updated.append(res['succeeded'].to_string(FLAGS.format))
        if res['failed'] is not None:
            untouched.append(res['failed'].to_string(FLAGS.format))
        if res['info'] is not None:
            print(res['info'])
    with open(os.path.join(FLAGS.dir, f'{FLAGS.bibfile}_updated.bib'), 'w') as f:
        for entry in updated:
            f.write(entry)
    with open(os.path.join(FLAGS.dir, f'{FLAGS.bibfile}_untouched.bib'), 'w') as f:
        for entry in untouched:
            f.write(entry)

if __name__ == '__main__':
    rebib()
