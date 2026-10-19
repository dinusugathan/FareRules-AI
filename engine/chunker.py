from typing import List, Dict, Any
from engine.models import CarrierFareRule

class TariffChunk:
    def __init__(self, chunk_id: str, title: str, text: str, metadata: Dict[str, Any], citation_tag: str):
        self.chunk_id = chunk_id
        self.title = title
        self.text = text
        self.metadata = metadata
        self.citation_tag = citation_tag

class TravelTariffChunker:
    """
    Context-Enriched Chunker for Travel Industry ATPCO & GDS Tariffs.
    Injects carrier code, sector, cabin class, and time-window metadata headers
    to ensure 100% precision in cancellation and refund retrieval.
    """
    def chunk_carrier_rule(self, rule: CarrierFareRule) -> List[TariffChunk]:
        chunks = []
        base_header = (
            f"[CARRIER: {rule.carrier_name} ({rule.carrier_code}) | Service: {rule.service_type} | "
            f"Sector: {rule.sector} | Class: {rule.fare_class} | Citation: {rule.citation}]"
        )

        # 1. Overview & Baggage Allowance Chunk
        baggage_str = ", ".join([f"{k}: {v}" for k, v in rule.baggage_allowance.items()])
        overview_text = (
            f"{base_header}\n"
            f"Fare Overview: {rule.carrier_name} {rule.fare_class} on {rule.sector} routes.\n"
            f"Baggage Allowance: {baggage_str}.\n"
            f"Operational Notes: {rule.notes or 'Standard fare conditions apply.'}"
        )
        chunks.append(TariffChunk(
            chunk_id=f"{rule.id}_BAGGAGE",
            title=f"{rule.carrier_name} {rule.fare_class} - Baggage & Overview",
            text=overview_text,
            metadata={"carrier_code": rule.carrier_code, "service_type": rule.service_type, "topic": "baggage"},
            citation_tag=rule.citation
        ))

        # 2. Cancellation & Voluntary Refund Slabs Chunk (ATPCO Cat 16 / Cat 33)
        slabs_text = "\n".join([f"• Window: {s.time_window} -> Penalty: {'₹' + str(int(s.airline_penalty)) if s.airline_penalty > 0 and s.airline_penalty >= 1 else (str(int(s.airline_penalty * 100)) + '% of fare' if s.airline_penalty > 0 else 'Non-refundable / No-Show')} ({s.description})" for s in rule.cancellation_slabs])
        cancel_text = (
            f"{base_header}\n"
            f"Voluntary Cancellation & Refund Penalties:\n"
            f"{slabs_text}\n"
            f"Statutory Taxes: Airport taxes (UDF/PSF) remain refundable even in No-Show cases."
        )
        chunks.append(TariffChunk(
            chunk_id=f"{rule.id}_CANCEL",
            title=f"{rule.carrier_name} {rule.fare_class} - Cancellation Slabs",
            text=cancel_text,
            metadata={"carrier_code": rule.carrier_code, "service_type": rule.service_type, "topic": "cancellation"},
            citation_tag=rule.citation
        ))

        # 3. Rescheduling & Date Change Slabs Chunk (ATPCO Cat 31)
        if rule.rescheduling_slabs:
            resched_slabs_text = "\n".join([f"• Window: {s.time_window} -> Change Fee: ₹{int(s.change_fee)} ({s.description})" for s in rule.rescheduling_slabs])
            resched_text = (
                f"{base_header}\n"
                f"Voluntary Date Change & Rescheduling Rules:\n"
                f"{resched_slabs_text}\n"
                f"Fare Difference: If the new flight has a higher fare, fare difference applies in addition to the change fee."
            )
            chunks.append(TariffChunk(
                chunk_id=f"{rule.id}_RESCHED",
                title=f"{rule.carrier_name} {rule.fare_class} - Rescheduling Fees",
                text=resched_text,
                metadata={"carrier_code": rule.carrier_code, "service_type": rule.service_type, "topic": "rescheduling"},
                citation_tag=rule.citation
            ))

        return chunks

    def chunk_agency_fees(self, agency_data: Dict[str, Any]) -> List[TariffChunk]:
        chunks = []
        charges = agency_data.get("service_charges", {})
        waivers = agency_data.get("waiver_rules", {})
        citation = agency_data.get("citation_tag", "AKBAR-SERVICE-FEE-2026")

        charges_text = (
            f"[PORTAL: Akbar Travels India Pvt Ltd | Category: Agency Service Charges | Citation: {citation}]\n"
            f"Cancellation Service Fees Charged by Akbar Travels Portal:\n"
            f"• Domestic Flight Cancellation (B2C Retail Website): ₹{charges.get('domestic_flight_cancellation_b2c', 350.0):.0f} per sector\n"
            f"• Domestic Flight Cancellation (B2B Agent Portal): ₹{charges.get('domestic_flight_cancellation_b2b', 200.0):.0f} per sector\n"
            f"• International Flight Cancellation (B2C Retail): ₹{charges.get('international_flight_cancellation_b2c', 750.0):.0f} per sector\n"
            f"• International Flight Cancellation (B2B Agent): ₹{charges.get('international_flight_cancellation_b2b', 450.0):.0f} per sector\n"
            f"• IRCTC Train Cancellation: ₹{charges.get('irctc_train_cancellation', 50.0):.0f} per ticket\n"
            f"• Intercity Bus Cancellation: ₹{charges.get('intercity_bus_cancellation', 30.0):.0f} per seat."
        )
        chunks.append(TariffChunk(
            chunk_id="AKBAR_CHARGES",
            title="Akbar Travels Portal Service Fees",
            text=charges_text,
            metadata={"topic": "agency_fees"},
            citation_tag=citation
        ))

        waivers_text = (
            f"[PORTAL: Akbar Travels India Pvt Ltd | Category: Special Waivers & Exceptions | Citation: {citation}]\n"
            f"Emergency & Airline Waiver Conditions:\n"
            f"• Medical Emergency: {waivers.get('medical_emergency')}\n"
            f"• Carrier Schedule Disruption: {waivers.get('flight_cancellation_by_airline')}\n"
            f"• B2B GDS Void Window: {waivers.get('b2b_agent_convenience')}"
        )
        chunks.append(TariffChunk(
            chunk_id="AKBAR_WAIVERS",
            title="Akbar Travels Emergency Waivers",
            text=waivers_text,
            metadata={"topic": "waivers"},
            citation_tag=citation
        ))

        return chunks
