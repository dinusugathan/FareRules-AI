from typing import List, Tuple
from engine.chunker import TariffChunk

class TravelTariffReranker:
    """
    Cross-Encoder Reranker using FlashRank (ms-marco-TinyBERT).
    Re-scores candidate tariff chunks directly against user departure timeline and query constraints.
    """
    def __init__(self, model_name: str = "ms-marco-TinyBERT-L-2-v2"):
        self.ranker = None
        try:
            from flashrank import Ranker
            self.ranker = Ranker(model_name=model_name, cache_dir="./.cache")
        except Exception:
            self.ranker = None

    def rerank(
        self, 
        query: str, 
        candidates: List[Tuple[TariffChunk, float]], 
        top_n: int = 3
    ) -> List[Tuple[TariffChunk, float]]:
        if not candidates:
            return []

        if self.ranker is not None:
            try:
                from flashrank import RerankRequest
                passages = [
                    {"id": idx, "text": chunk.text, "meta": chunk.metadata}
                    for idx, (chunk, _) in enumerate(candidates)
                ]
                req = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(req)
                
                reranked = []
                for item in results[:top_n]:
                    orig_chunk = candidates[item["id"]][0]
                    reranked.append((orig_chunk, float(item["score"])))
                return reranked
            except Exception:
                pass

        # Fallback: title affinity boost
        scored = []
        q_low = query.lower()
        for chunk, orig_score in candidates:
            bonus = 0.0
            for term in ["cancel", "refund", "resched", "fee", "hours", "change"]:
                if term in q_low and term in chunk.text.lower():
                    bonus += 0.15
            scored.append((chunk, orig_score + bonus))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]
