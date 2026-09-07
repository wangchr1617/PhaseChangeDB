# Elasticsearch v0.1 bootstrap

Target: Elasticsearch 9.x.

The mappings use a 1024-dimensional `dense_vector`. v0.1 assumes one pinned
multilingual scientific embedding profile. Changing the embedding model or
dimension requires a new index generation (for example v2) and a reindex;
never mix embeddings from different models in the same physical index.

Install each template:

```bash
curl -X PUT "$ES_URL/_index_template/pcm-papers-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-papers-template.json
curl -X PUT "$ES_URL/_index_template/pcm-evidence-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-evidence-template.json
curl -X PUT "$ES_URL/_index_template/pcm-materials-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-materials-template.json
curl -X PUT "$ES_URL/_index_template/pcm-observations-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-observations-template.json
curl -X PUT "$ES_URL/_index_template/pcm-claims-v1" \
  -H 'Content-Type: application/json' --data-binary @pcm-claims-template.json
```

Create initial physical indices and attach stable read aliases explicitly:

```bash
curl -X PUT "$ES_URL/pcm-papers-v1-000001"
curl -X PUT "$ES_URL/pcm-evidence-v1-000001"
curl -X PUT "$ES_URL/pcm-materials-v1-000001"
curl -X PUT "$ES_URL/pcm-observations-v1-000001"
curl -X PUT "$ES_URL/pcm-claims-v1-000001"

curl -X POST "$ES_URL/_aliases" -H 'Content-Type: application/json' -d '{
  "actions": [
    {"add":{"index":"pcm-papers-v1-000001","alias":"pcm-papers"}},
    {"add":{"index":"pcm-evidence-v1-000001","alias":"pcm-evidence"}},
    {"add":{"index":"pcm-materials-v1-000001","alias":"pcm-materials"}},
    {"add":{"index":"pcm-observations-v1-000001","alias":"pcm-observations"}},
    {"add":{"index":"pcm-claims-v1-000001","alias":"pcm-claims"}}
  ]
}'
```

Application code reads through the stable aliases. During a reindex, create the
new physical index first and atomically swap the alias with `_aliases`.

For retrieval, combine lexical and kNN/vector ranks with reciprocal-rank
fusion (RRF). Exact scientific tokens (formulae, DOI, property codes, space
groups) must remain keyword/BM25-searchable; do not use vector-only RAG.
