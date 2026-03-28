"""
fidal_core.py — FIDAL scraping & ICRON fetch logic (no Streamlit dependency).
Shared by server.py.
"""

import requests
import base64
import urllib.parse
import re
from bs4 import BeautifulSoup


# ── Vigenère encode/decode (key = b"3gabbo83") ─────────────────────────────

def decode_tessera(encoded_str: str) -> str:
    key = b"3gabbo83"
    try:
        code = encoded_str.split('/')[-1]
        code = urllib.parse.unquote(code)
        code += "=" * ((4 - len(code) % 4) % 4)
        dec_bytes = base64.b64decode(code)
        tessera = ""
        for i in range(len(dec_bytes)):
            tessera += chr((dec_bytes[i] - key[i % len(key)]) % 256)
        return tessera
    except Exception:
        return "Sconosciuta"


def encode_tessera(tessera_str: str) -> str:
    key = b"3gabbo83"
    tessera_str = str(tessera_str).strip()
    enc_bytes = bytearray()
    for i in range(len(tessera_str)):
        enc_bytes.append((ord(tessera_str[i]) + key[i % len(key)]) % 256)
    b64 = base64.b64encode(enc_bytes).decode('utf-8')
    return urllib.parse.quote(b64)


# ── Time helpers ────────────────────────────────────────────────────────────

def hms_to_seconds(t_str: str) -> float:
    t_str = str(t_str).lower().replace('h', ':')
    parts = t_str.split(':')
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except Exception:
        return 999999.0


# ── ICRON fetch ─────────────────────────────────────────────────────────────

def fetch_from_icron(id_gara: str) -> list[dict]:
    """
    Recupera l'elenco iscritti da ICRON.
    Restituisce una lista di dicts con chiavi normalizzate.
    Raises ValueError / requests.HTTPError on failure.
    """
    url = "https://www.icron.it/IcronNewGO/getIscrizioni"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": "https://www.icron.it/newgo/"
    }
    payload = {"idGara": str(id_gara).strip()}
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("esito") != "OK":
        raise ValueError(f"ICRON errore: {data.get('messaggio', 'sconosciuto')}")

    participants = data.get("elencoPartecipanti", [])
    rename_map = {
        'pettorale': 'PETT',
        'cognome':   'COGNOME',
        'nome':      'NOME',
        'tessera':   'TESSERA',
        'categoria': 'CATEGORIA',
        'squadra':   'SOCIETA',
        'sesso':     'SESSO',
        'dataNascita': 'DATA_NASCITA',
    }
    result = []
    for p in participants:
        row = {}
        for k, v in p.items():
            row[rename_map.get(k, k)] = v
        # Clean PETT
        if 'PETT' in row:
            row['PETT'] = str(row['PETT']).strip().replace('.0', '')
        result.append(row)
    return result


# ── FIDAL PB scraping ───────────────────────────────────────────────────────

def extract_all_pbs(athlete_url: str) -> tuple[list[dict], dict]:
    """
    Scrapes all PBs and recent bests (2025-2026) from an athlete FIDAL page.
    Returns (pb_list, recent_bests_dict).
    pb_list: [{Specialità, Ambiente, Prestazione, Data/Anno, Luogo}, ...]
    recent_bests: {specialty_str: (sec, perf, loc, year)}
    """
    try:
        resp = requests.get(athlete_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        pb_data: list[dict] = []
        recent_bests: dict = {}

        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if not headers and table.find('tr'):
                headers = [td.get_text(strip=True).lower()
                           for td in table.find('tr').find_all('td')]

            is_pb_table = (any('specialit' in h for h in headers) or
                           any('prestazione' in h for h in headers) or
                           table.parent.get('id') == 'tab3')
            is_hist_table = any(h in ['anno', 'anno/data', 'data'] for h in headers)

            if is_pb_table:
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells or len(cells) < 3:
                        continue
                    specialty = cells[0].get_text(strip=True)
                    if specialty.lower() == 'specialità' or not specialty:
                        continue
                    env  = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    perf = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    year = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    loc  = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    pb_data.append({
                        "Specialità": specialty,
                        "Ambiente":   env,
                        "Prestazione": perf,
                        "Data/Anno":  year,
                        "Luogo":      loc
                    })

            if is_hist_table or is_pb_table:
                h_tag = table.find_previous(['h1', 'h2', 'h3', 'h4', 'h5'])
                spec = h_tag.get_text(strip=True) if h_tag else ""
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if len(cells) < 3:
                        continue
                    year_cell = cells[0].get_text(strip=True)
                    if year_cell in ['2025', '2026']:
                        perf_cell = (cells[6].get_text(strip=True)
                                     if len(cells) > 6
                                     else cells[2].get_text(strip=True))
                        loc_cell = cells[-1].get_text(strip=True)
                        sec = hms_to_seconds(perf_cell)
                        if spec and sec < 999999:
                            prev = recent_bests.get(spec)
                            if prev is None or sec < prev[0]:
                                recent_bests[spec] = (sec, perf_cell, loc_cell, year_cell)

        return pb_data, recent_bests
    except Exception:
        return [], {}


def is_road_event(spec: str) -> bool:
    s = str(spec).lower()
    return any(k in s for k in ['strada', 'maratona', 'maratonina', 'km'])


def get_recent_best(spec: str, recent_bests: dict) -> dict | None:
    """Return recent best dict for a specialty, or None."""
    match = recent_bests.get(spec)
    if match:
        return {"perf": match[1], "luogo": match[2], "anno": match[3]}
    for k, v in recent_bests.items():
        if spec.lower() in k.lower() or k.lower() in spec.lower():
            return {"perf": v[1], "luogo": v[2], "anno": v[3]}
    return None
