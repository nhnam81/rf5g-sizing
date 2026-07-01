"""Link budget calculator — DL and UL for 5G NR."""
from __future__ import annotations
import math
from typing import Tuple
from ..models.input_schema import RFSizingInput
from ..models.lookup_tables import BandLookup, PowerClassLookup, AntennaConfigLookup, ShadowFadingLookup
from ..models.output_schema import LinkBudgetResult


def _resolve_catalog_params(inp: RFSizingInput) -> dict:
    """If radio/antenna vendor+model specified, load catalog and override defaults."""
    overrides = {}
    bs = inp.base_station

    if bs.radio_vendor and bs.radio_model:
        try:
            from ..models.antenna_pattern import get_catalog_radio
            radio = get_catalog_radio(bs.radio_vendor, bs.radio_model)
            overrides["tx_power_w"] = radio.get("max_tx_power_w", bs.tx_power_w)
            overrides["radio_mimo"] = radio.get("mimo_config", bs.antenna_config)
            # If radio has mimo_config, suggest matching antenna_config
            mimo = radio.get("mimo_config", "")
            if "8T8R" in mimo:
                overrides["antenna_config_hint"] = "8T8R"
            elif "4T4R" in mimo:
                overrides["antenna_config_hint"] = "4T4R"
            elif "2T2R" in mimo:
                overrides["antenna_config_hint"] = "2T2R"
        except (ValueError, FileNotFoundError):
            pass  # Catalog not found, use defaults

    if bs.antenna_vendor and bs.antenna_model:
        try:
            from ..models.antenna_pattern import get_catalog_antenna
            freq_mhz = 3500  # Default n78 center freq
            from ..models.lookup_tables import BandLookup
            bl = BandLookup()
            try:
                freq_mhz = bl.get_fc(inp.frequency.band)
            except Exception:
                pass
            ant = get_catalog_antenna(bs.antenna_vendor, bs.antenna_model)
            overrides["antenna_gain_dbi"] = ant.get("gain_dbi")
            # Multi-band: select subband by frequency
            subbands = ant.get("subbands", [])
            if subbands:
                for sb in subbands:
                    r = sb.get("range_mhz", [0, 0])
                    if r[0] <= freq_mhz <= r[1]:
                        overrides["antenna_gain_dbi"] = sb.get("gain_dbi", overrides.get("antenna_gain_dbi"))
                        overrides["h_beamwidth_deg"] = sb.get("h_beamwidth_deg")
                        overrides["v_beamwidth_deg"] = sb.get("v_beamwidth_deg")
                        break
                # Fallback if freq not in any subband
                if overrides["antenna_gain_dbi"] is None:
                    overrides["antenna_gain_dbi"] = subbands[0].get("gain_dbi")
            overrides["antenna_model"] = ant.get("model")
            overrides["antenna_type"] = ant.get("type")
        except (ValueError, FileNotFoundError):
            pass  # Catalog not found, use defaults

    return overrides


def calculate_link_budget(
    inp: RFSizingInput,
    band_lookup: BandLookup,
    pc_lookup: PowerClassLookup,
    ant_lookup: AntennaConfigLookup,
    sf_lookup: ShadowFadingLookup,
) -> Tuple[LinkBudgetResult, LinkBudgetResult]:
    """Calculate DL and UL link budgets.

    Returns (dl_result, ul_result) tuple.
    """
    # Resolve parameters from lookup tables
    fc_mhz = band_lookup.get_fc(inp.frequency.band)
    fc_ghz = fc_mhz / 1000.0
    nrb = band_lookup.get_nrb(inp.frequency.bandwidth_mhz, inp.frequency.scs_khz)
    bw_hz = inp.frequency.bandwidth_mhz * 1e6

    bs_config = ant_lookup.get_config(inp.base_station.antenna_config)
    ue_config = ant_lookup.get_ue_config()

    # Apply catalog overrides if radio/antenna vendor+model specified
    catalog_overrides = _resolve_catalog_params(inp)
    tx_power_w = catalog_overrides.get("tx_power_w", inp.base_station.tx_power_w)
    antenna_gain_override = catalog_overrides.get("antenna_gain_dbi")
    if antenna_gain_override is not None:
        # Replace antenna gain from catalog, keep MIMO/BF gains from config
        bs_config = {**bs_config, "antenna_gain_dbi": antenna_gain_override}

    ue_tx_dbm = pc_lookup.get_tx_power_dbm(inp.user_equipment.power_class)

    # Shadow fading margin (3GPP TR 38.901 Table 7.4.2-1)
    sf_margin = inp.margins.shadow_fading_db
    if sf_margin is None:
        sf_margin = sf_lookup.get_sf_margin(
            obstacle_density=inp.environment.obstacle_density,
            coverage_probability=inp.environment.coverage_probability,
            scenario=inp.environment.scenario,
            los_condition="NLOS",  # Conservative: use NLOS sigma
        )

    # ---- DOWNLINK ----
    dl_tx_power_dbm = 10 * math.log10(tx_power_w * 1000)  # W to dBm
    dl_tx_gain_db = bs_config["antenna_gain_dbi"] + bs_config["beamforming_gain_db"]
    dl_rx_gain_db = ue_config["gain_dbi"]
    dl_cable_loss_db = inp.base_station.cable_loss_db
    dl_body_loss_db = inp.user_equipment.body_loss_db

    # DL EIRP
    dl_eirp = dl_tx_power_dbm + dl_tx_gain_db - dl_cable_loss_db

    # DL Noise figure + thermal noise
    dl_nf_db = inp.user_equipment.noise_figure_db
    dl_thermal_noise_dbm = -174 + 10 * math.log10(bw_hz)  # dBm/Hz → dBm
    dl_noise_floor_dbm = dl_thermal_noise_dbm + dl_nf_db

    # DL Required SNR (from noise floor to sensitivity)
    # Assume ~-6 dB processing gain for typical 5G NR
    dl_snr_required_db = -6.0  # Typical for QPSK 1/2
    dl_sensitivity_dbm = dl_noise_floor_dbm + dl_snr_required_db

    # DL MAPL
    # Note: dl_cable_loss_db is already included in dl_eirp, do NOT subtract again
    dl_mapl = (dl_eirp + dl_rx_gain_db
               - dl_sensitivity_dbm
               - dl_body_loss_db
               - inp.margins.interference_db
               - sf_margin
               - inp.margins.rain_attenuation_db
               - inp.margins.penetration_db)

    dl = LinkBudgetResult(
        direction="DL",
        eirp_dbm=round(dl_eirp, 2),
        rx_sensitivity_dbm=round(dl_sensitivity_dbm, 2),
        mapl_db=round(dl_mapl, 2),
        tx_power_dbm=round(dl_tx_power_dbm, 2),
        tx_gain_db=round(dl_tx_gain_db, 2),
        rx_gain_db=round(dl_rx_gain_db, 2),
        cable_loss_db=round(dl_cable_loss_db, 2),  # included in EIRP, shown for reference
        body_loss_db=round(dl_body_loss_db, 2),
        interference_margin_db=round(inp.margins.interference_db, 2),
        shadow_fading_margin_db=round(sf_margin, 2),
        rain_margin_db=round(inp.margins.rain_attenuation_db, 2),
        penetration_loss_db=round(inp.margins.penetration_db, 2),
        noise_floor_dbm=round(dl_noise_floor_dbm, 2),
        noise_figure_db=round(dl_nf_db, 2),
        snr_required_db=round(dl_snr_required_db, 2),
    )

    # ---- UPLINK ----
    ul_tx_power_dbm = ue_tx_dbm
    ul_tx_gain_db = ue_config["gain_dbi"]
    ul_rx_gain_db = bs_config["antenna_gain_dbi"] + bs_config["beamforming_gain_db"]
    ul_cable_loss_db = inp.base_station.cable_loss_db
    ul_body_loss_db = inp.user_equipment.body_loss_db

    # UL EIRP
    ul_eirp = ul_tx_power_dbm + ul_tx_gain_db - ul_body_loss_db

    # UL Noise
    ul_nf_db = inp.base_station.noise_figure_db
    ul_thermal_noise_dbm = -174 + 10 * math.log10(bw_hz)
    ul_noise_floor_dbm = ul_thermal_noise_dbm + ul_nf_db
    ul_snr_required_db = -6.0
    ul_sensitivity_dbm = ul_noise_floor_dbm + ul_snr_required_db

    # UL MAPL
    ul_mapl = (ul_eirp + ul_rx_gain_db
               - ul_sensitivity_dbm
               - ul_cable_loss_db
               - inp.margins.interference_db
               - sf_margin
               - inp.margins.rain_attenuation_db
               - inp.margins.penetration_db)

    ul = LinkBudgetResult(
        direction="UL",
        eirp_dbm=round(ul_eirp, 2),
        rx_sensitivity_dbm=round(ul_sensitivity_dbm, 2),
        mapl_db=round(ul_mapl, 2),
        tx_power_dbm=round(ul_tx_power_dbm, 2),
        tx_gain_db=round(ul_tx_gain_db, 2),
        rx_gain_db=round(ul_rx_gain_db, 2),
        cable_loss_db=round(ul_cable_loss_db, 2),
        body_loss_db=round(ul_body_loss_db, 2),
        interference_margin_db=round(inp.margins.interference_db, 2),
        shadow_fading_margin_db=round(sf_margin, 2),
        rain_margin_db=round(inp.margins.rain_attenuation_db, 2),
        penetration_loss_db=round(inp.margins.penetration_db, 2),
        noise_floor_dbm=round(ul_noise_floor_dbm, 2),
        noise_figure_db=round(ul_nf_db, 2),
        snr_required_db=round(ul_snr_required_db, 2),
    )

    return dl, ul