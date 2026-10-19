from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CancellationSlab(BaseModel):
    time_window: str
    min_hours: int
    max_hours: int
    airline_penalty: float              # Fixed amount or percentage (0.0 to 1.0) or -1 for non-refundable/no-show
    description: str

class ReschedulingSlab(BaseModel):
    time_window: str
    min_hours: int
    max_hours: int
    change_fee: float
    description: str

class CarrierFareRule(BaseModel):
    id: str
    carrier_code: str
    carrier_name: str
    service_type: str                   # Flight, Train, Bus
    sector: str                         # Domestic, International (Gulf), etc.
    fare_class: str                     # Saver, Flexi Plus, Comfort, etc.
    baggage_allowance: Dict[str, str] = Field(default_factory=dict)
    cancellation_slabs: List[CancellationSlab] = Field(default_factory=list)
    rescheduling_slabs: List[ReschedulingSlab] = Field(default_factory=list)
    citation: str
    notes: Optional[str] = None

class RefundQuoteResult(BaseModel):
    ticket_fare: float
    hours_before_departure: Optional[float] = None
    airline_penalty: float
    agency_fee: float
    net_refund: float
    is_noshow: bool = False
    citation: str
    breakdown_summary: str

class FareRulesAgentResponse(BaseModel):
    query: str
    answer: str
    quote: Optional[RefundQuoteResult] = None
    policy_citations: List[str] = Field(default_factory=list)
    retrieved_rule_id: Optional[str] = None
    latency_ms: float = 0.0

class FareEvalCaseResult(BaseModel):
    test_id: str
    passed: bool
    correct_penalty: bool
    correct_agency_fee: bool
    correct_refund: bool
    citation_matched: bool
    latency_ms: float
    details: str
