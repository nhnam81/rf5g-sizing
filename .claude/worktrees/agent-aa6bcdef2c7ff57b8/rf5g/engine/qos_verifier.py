"""QoS Verifier — Check if each service type meets SINR and throughput requirements."""
from __future__ import annotations
from ..models.input_schema import RFSizingInput
from ..models.lookup_tables import QoSLookup
from ..models.output_schema import QoSVerificationResult
from .sinr_mapper import coverage_percentage


def verify_qos(
    inp: RFSizingInput,
    sinr_db: float,
    cell_radius_km: float,
    qos_lookup: QoSLookup | None = None,
) -> list[QoSVerificationResult]:
    """Verify QoS for each relevant service type.

    For each service:
    - Check if SINR at cell edge >= SINR minimum
    - Estimate % of cell area where SINR >= threshold
    - Check throughput availability

    Returns list of QoSVerificationResult.
    """
    if qos_lookup is None:
        qos_lookup = QoSLookup()

    # Get services to check
    if inp.qos.primary_service == "mixed":
        services = qos_lookup.get_services_for_mixed()
    else:
        services = [qos_lookup.get_service(inp.qos.primary_service)]

    results = []
    for svc in services:
        sinr_req = svc["sinr_min_db"]
        area_pct = coverage_percentage(sinr_db, sinr_req)
        passed = sinr_db >= sinr_req

        results.append(QoSVerificationResult(
            service=svc["service"],
            sinr_required_db=sinr_req,
            sinr_available_db=round(sinr_db, 2),
            radius_km=round(cell_radius_km, 4),
            area_percentage=area_pct,
            passed=passed,
        ))

    return results