from typing import Optional, Dict, Any
from engine.models import CarrierFareRule, RefundQuoteResult

class TravelFeeCalculatorTool:
    """
    Deterministic Tool for Travel Refund & Penalty Calculations.
    Eliminates financial hallucinations by strictly executing airline tariff slabs
    and Akbar Travels agency service charges.
    """
    def __init__(self, agency_data: Dict[str, Any]):
        self.charges = agency_data.get("service_charges", {})
        self.agency_citation = agency_data.get("citation_tag", "AKBAR-SERVICE-FEE-2026")

    def calculate_cancellation_refund(
        self,
        ticket_fare: float,
        hours_before_departure: float,
        rule: CarrierFareRule,
        channel: str = "B2C"
    ) -> RefundQuoteResult:
        """
        Determines the exact cancellation penalty slab and computes net customer refund.
        """
        matched_slab = None
        for slab in rule.cancellation_slabs:
            if slab.min_hours <= hours_before_departure < slab.max_hours:
                matched_slab = slab
                break

        # Fallback to no-show slab if within 0 to min_hours
        if not matched_slab and rule.cancellation_slabs:
            matched_slab = min(rule.cancellation_slabs, key=lambda s: s.min_hours)

        # 1. Determine Airline Penalty
        is_noshow = False
        if not matched_slab or matched_slab.airline_penalty == -1.0:
            is_noshow = True
            airline_penalty = ticket_fare
            net_refund = 0.0
            agency_fee = 0.0
            summary = (
                f"NO-SHOW / NON-REFUNDABLE: Flight departure is within {hours_before_departure:.0f} hours. "
                f"Under {rule.carrier_name} ({rule.citation}) tariff regulations, ticket fare (₹{ticket_fare:.2f}) is forfeited. "
                f"Only statutory airport taxes (UDF/PSF) may be requested via post-departure TDR."
            )
        else:
            if 0.0 < matched_slab.airline_penalty < 1.0:
                # Percentage deduction (e.g. IRCTC train 25% or 50%, or Bus slabs)
                airline_penalty = round(ticket_fare * matched_slab.airline_penalty, 2)
            else:
                # Fixed penalty (capped at ticket fare)
                airline_penalty = min(matched_slab.airline_penalty, ticket_fare)

            # 2. Determine Akbar Travels Agency Service Fee
            is_b2b = channel.upper() == "B2B"
            if rule.service_type == "Flight":
                if "International" in rule.sector:
                    agency_fee = self.charges.get("international_flight_cancellation_b2b" if is_b2b else "international_flight_cancellation_b2c", 750.0)
                else:
                    agency_fee = self.charges.get("domestic_flight_cancellation_b2b" if is_b2b else "domestic_flight_cancellation_b2c", 350.0)
            elif rule.service_type == "Train":
                agency_fee = self.charges.get("irctc_train_cancellation", 50.0)
            else:
                agency_fee = self.charges.get("intercity_bus_cancellation", 30.0)

            # 3. Calculate Net Refund
            net_refund = max(0.0, round(ticket_fare - airline_penalty - agency_fee, 2))

            summary = (
                f"Financial Breakdown ({matched_slab.time_window}):\n"
                f"• Gross Ticket Fare: ₹{ticket_fare:.2f}\n"
                f"• {rule.carrier_name} Penalty ({rule.citation}): -₹{airline_penalty:.2f}\n"
                f"• Akbar Travels Portal Fee ({self.agency_citation}): -₹{agency_fee:.2f} ({'B2B Agent Slab' if is_b2b else 'B2C Retail Slab'})\n"
                f"=========================================\n"
                f"• Net Refund Credited: ₹{net_refund:.2f}"
            )

        return RefundQuoteResult(
            ticket_fare=ticket_fare,
            hours_before_departure=hours_before_departure,
            airline_penalty=airline_penalty,
            agency_fee=agency_fee,
            net_refund=net_refund,
            is_noshow=is_noshow,
            citation=rule.citation,
            breakdown_summary=summary
        )
