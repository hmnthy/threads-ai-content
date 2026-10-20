# Cố ý để trống: import sẵn ở đây làm `import src.nlp.topic_identity` (API dùng) kéo theo `lingua`
# (292 MB) + `anthropic` vào gói Vercel (ADR-0025). Import thẳng từ module con, VD
# `from src.nlp.topics import cluster_embeddings`. Test: tests/test_api_bundle.py.
