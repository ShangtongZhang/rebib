import pybtex
from pybtex.database.input import bibtex
import bibtex_dblp.dblp_api
import requests
import numpy as np
import multiprocessing as mp
from absl import flags
import sys


flags.DEFINE_string('input', '/Users/Shangtong/GoogleDrive/Paper/phd_thesis/ref.bib', 'input file')
flags.DEFINE_string('output', '/Users/Shangtong/GoogleDrive/Paper/phd_thesis/ref2.bib', 'output file')
flags.DEFINE_integer('num_workers', 5, 'parallelization')
flags.DEFINE_string('format', 'bibtex', 'format of the file')
flags.FLAGS(sys.argv)
FLAGS = flags.FLAGS


def filter_fields(pub):
    desired = ['title', 'booktitle', 'year', 'journal', 'school']
    return {k: pub.fields[k] for k in desired if k in pub.fields.keys()}


def update_entry(entry):
    author = str(entry.persons['author'][0])
    title = entry.fields['title']
    query = f'{title} {author}'
    result = dict(succeeded=None, failed=None, info=None)
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
            # use the first one but give a warning
            pub = pubs[0]
            result['info'] = f'Two candidates for {query}: {pubs[0].title} v.s. {pubs[1].title}. The first one is used.'
        bytes = None
        try:
            bytes = requests.get(f'{pub.url}.bib')
        except Exception as e:
            result['info'] = e
            result['failed'] = entry
            return result
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
        result['succeeded'] = updated_entry

    return result


def rebib():
    parser = bibtex.Parser()
    bib_data = parser.parse_file(FLAGS.input)
    entries = [bib_data.entries[key] for key in bib_data.entries]
    if FLAGS.num_workers > 1:
        pool = mp.Pool(processes=FLAGS.num_workers)
        results = pool.map(update_entry, entries)
    else:
        results = [update_entry(entry) for entry in entries]
    updated = []
    untouched = []
    for res in results:
        if res['succeeded'] is not None:
            updated.append(res['succeeded'].to_string(FLAGS.format))
        if res['failed'] is not None:
            untouched.append(res['failed'].to_string(FLAGS.format))
        if res['info'] is not None:
            print(res['info'])
    with open(FLAGS.output, 'w') as f:
        for entry in updated:
            f.write(entry)
        f.write('%% The following entries are untouched \n')
        for entry in untouched:
            f.write(entry)

if __name__ == '__main__':
    rebib()
