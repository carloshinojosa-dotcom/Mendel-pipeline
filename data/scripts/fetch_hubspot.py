#!/usr/bin/env python3
"""
Trae el pipeline de HubSpot para tu equipo y genera:
  - data/deals.json   (oportunidades activas, en etapas canónicas)
  - data/closed.json  (oportunidades Closed Won del trimestre actual)
  - data/meta.json    (metadata: cuándo se generó, trimestre actual)

Se ejecuta todos los días vía GitHub Actions (.github/workflows/update-dashboard.yml).
Requiere la variable de entorno HUBSPOT_TOKEN (token de una Private App de HubSpot).

Cómo generar el token: HubSpot > Configuración > Integraciones > Apps privadas > Crear app privada.
Scopes necesarios (mínimo): crm.objects.deals.read, crm.objects.contacts.read, crm.objects.owners.read
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import requests

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN")
if not HUBSPOT_TOKEN:
    print("ERROR: falta la variable de entorno HUBSPOT_TOKEN", file=sys.stderr)
    sys.exit(1)

BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# CONFIGURACIÓN — ajustar acá si cambia el equipo, el pipeline o las etapas.
# Los owner IDs ya vienen cargados con tu equipo (Jorge, Iramar, Michell, Carlos).
# Para agregar a alguien más: HubSpot > Configuración > Objetos > Negocios >
# Propietarios (o pedime que lo busque con el conector de HubSpot).
# ---------------------------------------------------------------------------

OWNER_IDS = {
    "79723056": "Jorge Cervera",
    "94721595": "Iramar Yeo López Aguado",
    "93266693": "Michell Adrian Munayer Lara",
    "93012758": "Carlos Enrique Hinojosa Sanchez",
}

# Estos IDs de pipeline y de etapa son los del portal de Mendel (MX Sales /
# MX Viajes). Si tu equipo trabaja otro pipeline, revisalos en HubSpot >
# Configuración > Objetos > Negocios > Pipelines, y actualizá los diccionarios.
PIPELINES = {
    "4022877": "MX Sales",
    "887428883": "MX Viajes",
    "4168207": "AD Lifecycle",
}

STAGE_LABELS = {
    "213223445": "Discovery", "13516851": "Qualified", "13510788": "Negotiation",
    "13516852": "Risk Analysis & Documentation", "13510790": "Internal validation",
    "164574773": "POC", "13516853": "Closed won", "13516854": "Closed lost",
    "108155261": "Nurturing", "17932365": "AD Lifecycle stage", "13955720": "AD Lifecycle stage",
    "1335049769": "Discovery", "1335049770": "Qualified", "1335049771": "Negotiation",
    "1335049772": "Risk Analysis & Documentation", "1335049773": "Internal validation",
    "1335049774": "POC", "1335049775": "Closed won",
}

# Solo estas etapas cuentan como "pipeline activo" (se excluyen Nurturing, POC y AD Lifecycle)
CANONICAL_ACTIVE_STAGE_IDS = {
    "213223445", "13516851", "13510788", "13516852", "13510790",
    "1335049769", "1335049770", "1335049771", "1335049772", "1335049773",
}

# Risk Analysis & Documentation + Internal Validation (para "Verbal Win")
VERBAL_WIN_STAGE_IDS = {"13516852", "13510790", "1335049772", "1335049773"}

CLOSED_WON_STAGE_IDS = {"13516853", "85823390", "132151365", "11314356", "157459585", "1335049775"}

SENIOR_KEYWORDS = ["cfo", "chief financial", "director", "directora", "gerente general",
    "gerente financiero", "country manager", "controller", "contralor", "tesorer",
    "treasury", "head of finance", "general director", "director general", "ceo",
    "founder", "dueño", "dueña", "socio"]
MID_KEYWORDS = ["manager", "jefe", "lead", "coordinator", "gerente", "supervisor"]
JUNIOR_KEYWORDS = ["accountant", "analyst", "associate", "assistant", "contador",
    "contabilidad", "auxiliar", "operaciones", "sales administration", "payable"]


def classify_contact(title):
    if not title:
        return "sin_contacto", None
    tl = title.lower()
    if any(k in tl for k in SENIOR_KEYWORDS):
        return "decisor", title
    if any(k in tl for k in MID_KEYWORDS):
        return "influencer", title
    return "operativo", title


def fetch_all_deals(extra_filters=None):
    """Trae todos los deals del equipo que matcheen el filtro dado."""
    properties = [
        "dealname", "amount", "dealstage", "hubspot_owner_id", "createdate",
        "closedate", "notes_last_contacted", "notes_last_updated", "pipeline",
        "origen", "num_notes", "num_contacted_notes", "hs_deal_stage_probability",
    ]
    filters = [
        {"propertyName": "hubspot_owner_id", "operator": "IN", "values": list(OWNER_IDS.keys())},
    ]
    if extra_filters:
        filters.extend(extra_filters)

    results = []
    after = None
    while True:
        body = {
            "filterGroups": [{"filters": filters}],
            "properties": properties,
            "limit": 100,
        }
        if after:
            body["after"] = after
        r = requests.post(f"{BASE}/crm/v3/objects/deals/search", headers=HEADERS, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        paging = data.get("paging", {}).get("next", {}).get("after")
        if not paging:
            break
        after = paging
        time.sleep(0.2)  # cortesía con el rate limit
    return results


def fetch_primary_contact_title(deal_id):
    """Trae el cargo (jobtitle) del primer contacto asociado a un deal, si existe."""
    try:
        r = requests.get(
            f"{BASE}/crm/v3/objects/deals/{deal_id}/associations/contacts",
            headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        assoc = r.json().get("results", [])
        if not assoc:
            return None
        contact_id = assoc[0]["id"]
        r2 = requests.get(
            f"{BASE}/crm/v3/objects/contacts/{contact_id}",
            headers=HEADERS, params={"properties": "jobtitle"}, timeout=15,
        )
        r2.raise_for_status()
        return r2.json().get("properties", {}).get("jobtitle")
    except requests.RequestException:
        return None


def ms_to_date(value):
    if value is None or value == '':
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        s = str(value).replace('Z', '+00:00')
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def current_quarter_bounds(now):
    q = (now.month - 1) // 3 + 1
    start_month = 3 * (q - 1) + 1
    start = datetime(now.year, start_month, 1, tzinfo=timezone.utc)
    end_month = start_month + 2
    end_year = now.year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    if end_month == 12:
        end = datetime(end_year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(end_year, end_month + 1, 1, tzinfo=timezone.utc)
    return start, end, q


def main():
    now = datetime.now(timezone.utc)
    q_start, q_end, q_num = current_quarter_bounds(now)
    print(f"Ejecutando fetch — {now.isoformat()} — Q actual: Q{q_num} {now.year}")

    # --- 1) Deals activos (no cerrados) ---
    raw_open = fetch_all_deals(
        extra_filters=[{"propertyName": "hs_is_closed", "operator": "EQ", "value": "false"}],
    )
    print(f"Deals abiertos encontrados: {len(raw_open)}")

    active = []
    for obj in raw_open:
        p = obj["properties"]
        stage_id = p.get("dealstage", "")
        if stage_id not in CANONICAL_ACTIVE_STAGE_IDS:
            continue  # excluye Nurturing / POC / AD Lifecycle

        owner_id = p.get("hubspot_owner_id", "")
        create_dt = ms_to_date(p.get("createdate"))
        contact_dt = ms_to_date(p.get("notes_last_contacted"))
        close_dt = ms_to_date(p.get("closedate"))
        ref_dt = contact_dt or create_dt
        days_since = (now - ref_dt).days if ref_dt else None

        amount = p.get("amount") or "0"
        try:
            amount = float(amount)
        except ValueError:
            amount = 0.0

        title = fetch_primary_contact_title(obj["id"])
        dm_label, dm_title = classify_contact(title)

        active.append({
            "id": obj["id"],
            "name": p.get("dealname", ""),
            "amount": amount,
            "stageId": stage_id,
            "stage": STAGE_LABELS.get(stage_id, stage_id),
            "pipelineId": p.get("pipeline", ""),
            "pipeline": PIPELINES.get(p.get("pipeline", ""), p.get("pipeline", "")),
            "ownerId": owner_id,
            "owner": OWNER_IDS.get(owner_id, owner_id),
            "createDate": create_dt.strftime("%Y-%m-%d") if create_dt else None,
            "lastContacted": contact_dt.strftime("%Y-%m-%d") if contact_dt else None,
            "daysSinceContact": days_since,
            "origen": p.get("origen") or None,
            "stageProbability": round(float(p.get("hs_deal_stage_probability") or 0.3) * 100),
            "numNotes": int(p.get("num_notes") or 0),
            "numContacted": int(p.get("num_contacted_notes") or 0),
            "decisionMaker": dm_label,
            "contactTitle": dm_title,
            "expectedCloseDate": close_dt.strftime("%Y-%m-%d") if close_dt else None,
            "expectedCloseMonth": close_dt.strftime("%Y-%m") if close_dt else None,
        })
        time.sleep(0.05)

    # --- 2) Closed Won del trimestre actual ---
    raw_closed = fetch_all_deals(
        extra_filters=[
            {"propertyName": "dealstage", "operator": "IN", "values": list(CLOSED_WON_STAGE_IDS)},
            {"propertyName": "closedate", "operator": "GTE", "value": str(int(q_start.timestamp() * 1000))},
            {"propertyName": "closedate", "operator": "LT", "value": str(int(q_end.timestamp() * 1000))},
        ],
    )
    closed = []
    for obj in raw_closed:
        p = obj["properties"]
        owner_id = p.get("hubspot_owner_id", "")
        close_dt = ms_to_date(p.get("closedate"))
        amount = p.get("amount") or "0"
        try:
            amount = float(amount)
        except ValueError:
            amount = 0.0
        closed.append({
            "id": obj["id"],
            "name": p.get("dealname", ""),
            "amount": amount,
            "owner": OWNER_IDS.get(owner_id, owner_id),
            "closeDate": close_dt.strftime("%Y-%m-%d") if close_dt else None,
        })

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "deals.json"), "w", encoding="utf-8") as f:
        json.dump(active, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "closed.json"), "w", encoding="utf-8") as f:
        json.dump(closed, f, ensure_ascii=False, separators=(",", ":"))

    meta = {
        "generatedAt": now.isoformat(),
        "currentQuarter": f"{now.year}-Q{q_num}",
        "quarterStart": q_start.strftime("%Y-%m-%d"),
        "quarterEnd": q_end.strftime("%Y-%m-%d"),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Listo: {len(active)} deals activos, {len(closed)} cerrados este Q.")


if __name__ == "__main__":
    main()
