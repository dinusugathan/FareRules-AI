import json
import re
import time
from typing import List, Dict, Any, Optional

from engine.models import (
    CarrierFareRule, RefundQuoteResult, FareRulesAgentResponse
)
from engine.chunker import TravelTariffChunker, TariffChunk
from engine.hybrid_retriever import TravelHybridRetriever
from engine.reranker import TravelTariffReranker
from engine.tools import TravelFeeCalculatorTool

class FareRulesAgent:
    """
    FareRules AI Agent for Akbar Travels.
    Pipeline:
      1. Parameter & Intent Extraction (Carrier code, Hours to departure, Fare amount, Channel)
      2. Hybrid Retrieval (BM25 + Semantic Cosine + RRF)
      3. Cross-Encoder Reranking (FlashRank)
      4. Deterministic Penalty & Net Refund Tool Execution
      5. Structured Quotation with Grounded GDS/ATPCO Citations
    """
    def __init__(self, fare_rules_path: str, agency_fees_path: str):
        self.chunker = TravelTariffChunker()
        self.reranker = TravelTariffReranker()
        
        self.rules: Dict[str, CarrierFareRule] = {}
        self.chunks: List[TariffChunk] = []
        self._load_data(fare_rules_path, agency_fees_path)
        
        self.retriever = TravelHybridRetriever(self.chunks)
        self.fee_tool = TravelFeeCalculatorTool(self.agency_data)

    def _load_data(self, rules_path: str, fees_path: str):
        with open(rules_path, "r", encoding="utf-8") as f:
            raw_rules = json.load(f)
            for r in raw_rules:
                rule = CarrierFareRule(**r)
                self.rules[rule.carrier_code] = rule
                # Also index under ID
                self.rules[rule.id] = rule
                self.chunks.extend(self.chunker.chunk_carrier_rule(rule))

        with open(fees_path, "r", encoding="utf-8") as f:
            self.agency_data = json.load(f)
            self.chunks.extend(self.chunker.chunk_agency_fees(self.agency_data))

    def _extract_parameters(self, query: str) -> Dict[str, Any]:
        q_low = query.lower()
        params = {
            "carrier_code": "ALL",
            "hours": None,
            "fare": None,
            "channel": "B2C",
            "is_rescheduling": False,
            "is_medical": False
        }

        # 1. Carrier identification
        if "indigo" in q_low or "6e" in q_low:
            if "flexi" in q_low:
                params["carrier_code"] = "RULE-6E-FLEXI"
            else:
                params["carrier_code"] = "RULE-6E-SAVER"
        elif "air india express" in q_low or "ix" in q_low or "dubai" in q_low and "express" in q_low:
            params["carrier_code"] = "RULE-IX-GULF"
        elif "air india" in q_low or " ai " in q_low:
            params["carrier_code"] = "RULE-AI-COMFORT"
        elif "emirates" in q_low or " ek " in q_low:
            params["carrier_code"] = "RULE-EK-SAVER"
        elif "train" in q_low or "irctc" in q_low or "railway" in q_low:
            params["carrier_code"] = "RULE-IRCTC-CONFIRMED"
        elif "bus" in q_low:
            params["carrier_code"] = "RULE-BUS-INTERCITY"

        # 2. Channel (B2B vs B2C)
        if "b2b" in q_low or "agent portal" in q_low or "travel agent" in q_low:
            params["channel"] = "B2B"

        # 3. Hours to departure extraction
        if any(w in q_low for w in ["missed", "ago", "already departed", "< 4", "< 2", "<4", "<2"]):
            params["hours"] = 0.0
        else:
            hrs_match = re.search(r"(\d+)\s*(?:hours|hrs|hr)\b", q_low)
            if hrs_match:
                params["hours"] = float(hrs_match.group(1))
            else:
                days_match = re.search(r"(\d+)\s*(?:days|day)\b", q_low)
                if days_match:
                    params["hours"] = float(days_match.group(1)) * 24.0

        # 4. Ticket fare extraction (e.g. ₹5,200, 5200, ₹1,400)
        fare_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})", query)
        if fare_match:
            raw_num = fare_match.group(1).replace(",", "")
            params["fare"] = float(raw_num)

        # 5. Rescheduling vs Cancellation intent
        if any(w in q_low for w in ["reschedule", "date change", "change flight", "change fee"]):
            params["is_rescheduling"] = True

        if any(w in q_low for w in ["hospital", "medical", "icu", "doctor certificate"]):
            params["is_medical"] = True

        return params

    def process_query(self, query: str) -> FareRulesAgentResponse:
        start_time = time.time()
        params = self._extract_parameters(query)

        # 1. Retrieve candidates
        candidates = self.retriever.retrieve(query, carrier_filter=None, top_k=6)

        # 2. Rerank
        reranked = self.reranker.rerank(query, candidates, top_n=3)

        policy_citations = []
        for chunk, _ in reranked:
            if chunk.citation_tag not in policy_citations:
                policy_citations.append(chunk.citation_tag)

        # 3. Handle Special Medical Waiver Inquiry
        if params["is_medical"]:
            waiver_info = self.agency_data.get("waiver_rules", {}).get("medical_emergency")
            cit = self.agency_data.get("citation_tag", "AKBAR-SERVICE-FEE-2026")
            ans = (
                f"🏥 **Medical Emergency Waiver Protocol ({cit})**:\n"
                f"{waiver_info}\n\n"
                f"• Akbar Travels portal cancellation fee is **100% waived** upon approved medical waiver.\n"
                f"• Required Documents: Hospital admission summary, medical certificate on physician letterhead, and photo ID."
            )
            return FareRulesAgentResponse(
                query=query,
                answer=ans,
                policy_citations=[cit],
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        # 4. Handle B2B vs B2C General Service Fee Inquiry
        if params["carrier_code"] == "ALL" and "fee" in query.lower():
            charges = self.agency_data.get("service_charges", {})
            cit = self.agency_data.get("citation_tag", "AKBAR-SERVICE-FEE-2026")
            ans = (
                f"📋 **Akbar Travels Portal Service Fee Schedule ({cit})**:\n"
                f"• Domestic Flight Cancellation: **₹{charges.get('domestic_flight_cancellation_b2c', 350):.0f}** (B2C Retail) vs **₹{charges.get('domestic_flight_cancellation_b2b', 200):.0f}** (B2B Agent Portal)\n"
                f"• International Flight Cancellation: **₹{charges.get('international_flight_cancellation_b2c', 750):.0f}** (B2C Retail) vs **₹{charges.get('international_flight_cancellation_b2b', 450):.0f}** (B2B Agent Portal)\n"
                f"• IRCTC Rail Cancellation Fee: **₹{charges.get('irctc_train_cancellation', 50):.0f}** per ticket\n"
                f"• Bus Cancellation Fee: **₹{charges.get('intercity_bus_cancellation', 30):.0f}** per seat"
            )
            return FareRulesAgentResponse(
                query=query,
                answer=ans,
                policy_citations=[cit],
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        # 5. Handle Rescheduling Queries (e.g. IndiGo Flexi Plus)
        rule_key = params["carrier_code"]
        target_rule = self.rules.get(rule_key)

        if params["is_rescheduling"] and target_rule:
            resched_details = []
            for s in target_rule.rescheduling_slabs:
                resched_details.append(f"• **{s.time_window}**: ₹{s.change_fee:.0f} change fee ({s.description})")
            
            ans = (
                f"✈️ **{target_rule.carrier_name} {target_rule.fare_class} Rescheduling Policy ({target_rule.citation})**:\n"
                + "\n".join(resched_details) +
                "\n\n*Note*: Any difference in airfare between original ticket and new flight date applies in addition to the change fee."
            )
            return FareRulesAgentResponse(
                query=query,
                answer=ans,
                policy_citations=[target_rule.citation],
                retrieved_rule_id=target_rule.id,
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        # 6. Handle Cancellation & Deterministic Net Refund Tool Execution
        quote: Optional[RefundQuoteResult] = None
        if target_rule and params["hours"] is not None and params["fare"] is not None:
            quote = self.fee_tool.calculate_cancellation_refund(
                ticket_fare=params["fare"],
                hours_before_departure=params["hours"],
                rule=target_rule,
                channel=params["channel"]
            )
            ans = (
                f"📊 **Official Cancellation & Net Refund Quotation**:\n\n"
                f"{quote.breakdown_summary}\n\n"
                f"• **Carrier Authority**: {target_rule.carrier_name} Tariff Specification `[{quote.citation}]`\n"
                f"• **Akbar Portal Policy**: `[{self.fee_tool.agency_citation}]`"
            )
        else:
            # Fallback policy text if hours or fare was missing
            best_chunk = reranked[0][0]
            ans = (
                f"Here are the fare rules for your query:\n\n"
                f"{best_chunk.text}\n\n"
                f"To compute your exact rupee refund, please specify your **ticket fare** (e.g. ₹5,200) "
                f"and **hours left before departure**."
            )

        latency = round((time.time() - start_time) * 1000, 2)
        return FareRulesAgentResponse(
            query=query,
            answer=ans,
            quote=quote,
            policy_citations=policy_citations,
            retrieved_rule_id=target_rule.id if target_rule else None,
            latency_ms=latency
        )
