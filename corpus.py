import gzip
import random
import numpy as np

def read_corpus(path):
    """Creates a dictionary mapping ID to a tuple
    tuple: dictionary for question title, dictionary for body"""
    raw_corpus = {}
    fopen = gzip.open if path.endswith(".gz") else open
    with fopen(path) as fin:
        for line in fin:
            id, title, body = line.split("\t")
            title = title.lower().strip().split()
            body = body.lower().strip().split()
            raw_corpus[id] = (title, body)
    return raw_corpus

def load_embedding_iterator(path):
    file_open = gzip.open if path.endswith(".gz") else open
    with file_open(path) as fin:
        for line in fin:
            line = line.strip()
            if line:
                parts = line.split()
                word = parts[0]
                vals = np.array([ float(x) for x in parts[1:] ])
                yield word, vals

def load_embeddings(embeddings):
    """Returns:
    1. list of words in embeddings
    2. dictionary mapping a word to an id (its place in the embedding values list)
    3. list of vectors for each word embedding
    4. padding id (length of vocabulary)"""
    lst_words = [ ]
    vocab_map = {}
    emb_vals = [ ]
    for word, vector in embeddings:
        assert word not in vocab_map, "Duplicate words in initial embeddings"
        vocab_map[word] = len(vocab_map)
        emb_vals.append(vector)
        lst_words.append(word)

    n_d = len(emb_vals[0])

    padding_id = len(vocab_map)
    vocab_map["<padding>"] = len(vocab_map)
    lst_words.append("<padding>")
    emb_vals.append(random_init((n_d,))*0.001)

    emb_vals = np.vstack(emb_vals)
    return (lst_words, vocab_map, emb_vals, padding_id)

def questions_to_ids(vocab_map, words):
    """Maps a list of string tokens (from words) to a numpy array of integer IDs, using the 
    vocab map generated by load_embeddings"""
    return np.array([vocab_map.get(x) for x in words if x in vocab_map])

def map_corpus(vocab_map, raw_corpus, max_len=100):
    """Returns a dictionary mapping question id to a tuple of two arrays:
    ids for question title, and ids for question body"""
    ids_corpus = { }
    for id, pair in raw_corpus.iteritems():
        item = (questions_to_ids(vocab_map, pair[0]),
                          questions_to_ids(vocab_map,pair[1])[:max_len])
        ids_corpus[id] = item  
    return ids_corpus

def get_embeddings(titles, bodies, vocab_map, emb_vals):
    """Returns a numpy arrays [[title_word x # words] x # questions] and [[body_word x # words] x # questions]
    """
    
    # try:
    #     title_embeddings = [[emb_vals[word_id] for word_id in title] for title in titles]
    # except IndexError:
    #     for title in titles:
    #         for word_id in title:
    #             trying = emb_vals[word_id]
    #             # try:
    #             #     trying = emb_vals[word_id]
    #             # except IndexError:
    #             #     print title
    #             #     print word_id
    title_embeddings = [[emb_vals[int(word_id)] for word_id in title] for title in titles]
    body_embeddings = [[emb_vals[int(word_id)] for word_id in body] for body in bodies]

    # below for debugging purposes
    # title_embeddings = []
    # body_embeddings = []

    # for title in titles:
    #     title_embedding = []
    #     for word_id in title:
    #         title_embedding.append(emb_vals[word_id])
    #         # try:
    #         #     title_embedding.append(emb_vals[word_id])
    #         # except:
    #         #     print "title"
    #         #     print(word_id, type(word_id))
    #         #     print(emb_vals[word_id])
    #     title_embeddings.append(title_embedding)

    # for body in bodies:
    #     body_embedding = []
    #     for word_id in body:
    #         body_embeddings.append(emb_vals[word_id])
    #         # try:
    #         #     body_embeddings.append(emb_vals[word_id])
    #         # except:
    #         #     print "body"
    #         #     print(word_id, type(word_id))
    #         #     print(emb_vals[word_id])
    #     body_embeddings.append(body_embedding)

    return title_embeddings, body_embeddings

def read_annotations(path, K_neg=20):
    """Returns a tuple with:
    1. Question ID
    2. Other question IDs (for training)
    3. Training labels (1 for positive, 0 for negative)"""
    result = [ ]
    with open(path) as fin:
        for line in fin:
            parts = line.split("\t")
            pid, pos, neg = parts[:3]
            pos = pos.split()
            neg = neg.split()
            random.shuffle(neg)
            neg = neg[:K_neg]
            seen_questions = set()
            qids = [ ]
            qlabels = [ ]
            for question in neg:
                if question not in seen_questions:
                    qids.append(question)
                    qlabels.append(0 if question not in pos else 1)
                    seen_questions.add(question)
            for question in pos:
                if question not in seen_questions:
                    qids.append(question)
                    qlabels.append(1)
                    seen_questions.add(question)
            result.append((pid, qids, qlabels))

    return result

def android_annotations(positives, negatives):
    result = []
    for query in positives:
        if query in negatives and len(negatives[query]) >= 20:
            pos = positives[query]
            random.shuffle(pos)
            neg = negatives[query]
            random.shuffle(neg)
            qids = neg[:20] + [pos[0]]
            qlabels = [0]*20+[1]
            result.append((query, qids, qlabels))
    return result

def domain_classifier_batch(ids_corpus, data, batch_size, padding_id):
    data_order = range(len(data))
    random.shuffle(data_order)

    N = len(data)
    count = 0
    pid2id = {}
    titles = [ ]
    bodies = [ ]
    triples = [ ]
    batches = [ ]
    for data_point in xrange(N):
        i = data_order[data_point]
        pid, qids, qlabels = data[i]
        if pid not in ids_corpus: continue
        count += 1
        for id in [pid] + qids:
            if id not in pid2id:
                if id not in ids_corpus: continue
                # assign id based on number of data points seem so far
                pid2id[id] = len(titles)
                title, body = ids_corpus[id]
                titles.append(title)
                bodies.append(body)
        pid = pid2id[pid]
        pos = [ pid2id[q] for q, l in zip(qids, qlabels) if l == 1 and q in pid2id ]
        neg = [ pid2id[q] for q, l in zip(qids, qlabels) if l == 0 and q in pid2id ]
        triples += [ [pid,x]+neg for x in pos ]

        #once we've accumulated enough data to create a batch, or we've reached end of data
        if abs(len(triples)-batch_size) < 10 or len(triples) >= batch_size or data_point == N-1:
            titles, bodies = create_one_batch(titles, bodies, padding_id)

            triples = create_hinge_batch(triples)
            return (titles, bodies, triples)
            #batches.append((titles, bodies, triples))
            # titles = [ ]
            # bodies = [ ]
            # triples = [ ]
            # pid2id = {}
            # count = 0
    #return batches

def create_batches(ids_corpus, data, batch_size, padding_id):
    data_order = range(len(data))
    random.shuffle(data_order)

    N = len(data)
    count = 0
    pid2id = {}
    titles = [ ]
    bodies = [ ]
    triples = [ ]
    batches = [ ]
    for data_point in xrange(N):
        i = data_order[data_point]
        pid, qids, qlabels = data[i]
        if pid not in ids_corpus: continue
        count += 1
        for id in [pid] + qids:
            if id not in pid2id:
                if id not in ids_corpus: continue
                # assign id based on number of data points seem so far
                pid2id[id] = len(titles)
                title, body = ids_corpus[id]
                titles.append(title)
                bodies.append(body)
        pid = pid2id[pid]
        pos = [ pid2id[q] for q, l in zip(qids, qlabels) if l == 1 and q in pid2id ]
        neg = [ pid2id[q] for q, l in zip(qids, qlabels) if l == 0 and q in pid2id ]
        triples += [ [pid,x]+neg for x in pos ]

        #once we've accumulated enough data to create a batch, or we've reached end of data
        if count == batch_size or data_point == N-1:
            titles, bodies = create_one_batch(titles, bodies, padding_id)

            triples = create_hinge_batch(triples)
            batches.append((titles, bodies, triples))
            titles = [ ]
            bodies = [ ]
            triples = [ ]
            pid2id = {}
            count = 0
    title1 = batches[0][0]
    return batches

def create_eval_batches(ids_corpus, data, padding_id):
    lst = [ ]
    for pid, qids, qlabels in data:
        titles = [ ]
        bodies = [ ]
        for id in [pid]+qids:
            t, b = ids_corpus[id]
            titles.append(t)
            bodies.append(b)
        titles, bodies = create_one_batch(titles, bodies, padding_id)
        lst.append((titles, bodies, np.array(qlabels, dtype="int32")))
    return lst

def create_one_batch(titles, bodies, padding_id):
    max_title_len = max(1, max(len(x) for x in titles))
    max_body_len = max(1, max(len(x) for x in bodies))
    titles = (np.column_stack([ np.pad(x,(0,max_title_len-len(x)),'constant',
                            constant_values=padding_id) for x in titles]))
    bodies = (np.column_stack([ np.pad(x,(0,max_body_len-len(x)),'constant',
                            constant_values=padding_id) for x in bodies]))
    return titles, bodies

def create_hinge_batch(triples):
    max_len = max(len(x) for x in triples)
    triples = np.vstack([ np.pad(x,(0,max_len-len(x)),'edge')
                        for x in triples ]).astype('int32')
    return triples

def load_android_pairs(filename, positive=True):
    """Load question pairs with question id's.
    """
    with open(filename, "rt") as f:
        X = []
        for line in f:
            X.append(line.strip().split(" "))
        y = [1 if positive else 0]*len(X)
    return X, y

def random_init(size, rng=None, rng_type=None):
    if rng is None: rng = np.random.RandomState(random.randint(0,9999))
    if rng_type is None:
        #vals = rng.standard_normal(size)
        vals = rng.uniform(low=-0.05, high=0.05, size=size)

    elif rng_type == "normal":
        vals = rng.standard_normal(size)

    elif rng_type == "uniform":
        vals = rng.uniform(low=-3.0**0.5, high=3.0**0.5, size=size)

    else:
        raise Exception(
            "unknown random inittype: {}".format(rng_type)
          )

    return vals

