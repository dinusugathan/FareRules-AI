import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from engine.chunker import TariffChunk

class TravelHybridRetriever:
    """
    Hybrid Retriever combining Sparse BM25 + Subword Dense Vectors with Reciprocal Rank Fusion (RRF)
    tailored for Travel Industry GDS codes (6E, AI, IX, EK, IRCTC).
    """
    def __init__(self, chunks: List[TariffChunk], dim: int = 256):
        self.chunks = chunks
        self.dim = dim
        
        # 1. BM25 Sparse Index
        self.tokenized_corpus = [self._tokenize(c.text) for c in self.chunks]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        
        # 2. Dense Semantic Index
        self.embeddings = np.array([self._embed_text(c.text) for c in self.chunks], dtype=np.float32)

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
        return [tok for tok in cleaned.split() if len(tok) > 1]

    def _hash_token(self, token: str) -> int:
        h = 2166136261
        for char in token:
            h = (h ^ ord(char)) * 16777619
            h &= 0xFFFFFFFF
        return h % self.dim

    def _embed_text(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec
        for tok in tokens:
            idx = self._hash_token(tok)
            vec[idx] += 1.0
            if len(tok) >= 4:
                for i in range(len(tok) - 3):
                    vec[self._hash_token(tok[i:i+4])] += 0.5
        vec = np.log1p(vec)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def retrieve(
        self, 
        query: str, 
        carrier_filter: Optional[str] = None, 
        top_k: int = 6, 
        rrf_k: int = 60
    ) -> List[Tuple[TariffChunk, float]]:
        # Sparse BM25 scoring
        q_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(q_tokens)
        bm25_ranks = np.argsort(bm25_scores)[::-1]

        # Dense Cosine scoring
        q_vec = self._embed_text(query)
        dense_scores = np.dot(self.embeddings, q_vec)
        dense_ranks = np.argsort(dense_scores)[::-1]

        # Reciprocal Rank Fusion
        rrf_scores: Dict[int, float] = {i: 0.0 for i in range(len(self.chunks))}
        for rank, idx in enumerate(bm25_ranks[:top_k * 3]):
            rrf_scores[idx] += 1.0 / (rrf_k + rank + 1)
        for rank, idx in enumerate(dense_ranks[:top_k * 3]):
            rrf_scores[idx] += 1.0 / (rrf_k + rank + 1)

        sorted_candidates = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

        results = []
        for idx, score in sorted_candidates:
            chunk = self.chunks[idx]
            # Carrier filter if explicitly isolated
            if carrier_filter and carrier_filter != "ALL":
                meta_carrier = chunk.metadata.get("carrier_code")
                if meta_carrier and meta_carrier.lower() != carrier_filter.lower():
                    continue
            results.append((chunk, score))
            if len(results) >= top_k:
                break

        return results
