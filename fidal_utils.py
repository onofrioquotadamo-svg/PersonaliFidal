import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import base64
import os
import base64
import urllib.parse
import os
import json
import re

CACHE_FILE = "athlete_activity_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except: pass

def decode_tessera(encoded_str):
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

def encode_tessera(tessera_str):
    key = b"3gabbo83"
    tessera_str = str(tessera_str).strip()
    enc_bytes = bytearray()
    for i in range(len(tessera_str)):
        enc_bytes.append((ord(tessera_str[i]) + key[i % len(key)]) % 256)
    b64 = base64.b64encode(enc_bytes).decode('utf-8')
    return urllib.parse.quote(b64)

def hms_to_seconds(t_str):
    if not t_str or t_str == '-': return 999999
    t_str = str(t_str).lower().replace('h', ':')
    parts = t_str.split(':')
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except Exception:
        return 999999

def get_base64_logo(file_path):
    """Converte un'immagine in stringa Base64 per l'incorporamento HTML."""
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()
    except:
        pass
    return None

def fetch_from_icron(id_gara):
    url = "https://www.icron.it/IcronNewGO/getIscrizioni"
    headers = {
        "Content-Type": "application/json;charset=UTF-8", 
        "Referer": "https://www.icron.it/newgo/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    payload = {"idGara": str(id_gara).strip()}
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("esito") != "OK":
        raise ValueError(f"ICRON errore: {data.get('messaggio', 'sconosciuto')}")
    participants = data.get("elencoPartecipanti", [])
    if not participants: return pd.DataFrame()
    df = pd.DataFrame(participants)
    rename_map = {
        'pettorale': 'PETT', 'cognome': 'COGNOME', 'nome': 'NOME',
        'tessera': 'TESSERA', 'categoria': 'CATEGORIA', 'squadra': 'SOCIETA',
        'sesso': 'SESSO', 'dataNascita': 'DATA_NASCITA',
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    if 'PETT' in df.columns:
        df['PETT'] = df['PETT'].astype(str).str.strip().str.replace('.0', '', regex=False)
    return df

def get_last_activity_date(soup):
    try:
        for table in soup.find_all('table'):
            for tr in table.find_all('tr'):
                cells = tr.find_all(['td', 'th'])
                if len(cells) >= 2:
                    year_val = cells[0].get_text(strip=True)
                    date_val = cells[1].get_text(strip=True)
                    if year_val.isdigit() and len(year_val) == 4 and '/' in date_val:
                        return f"{date_val}/{year_val}"
        return None
    except: return None

def extract_all_pbs(athlete_url):
    try:
        resp = requests.get(athlete_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        pb_data, recent_bests, perf_dates = [], {}, {}
        
        last_activity = get_last_activity_date(soup)

        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if not headers and table.find('tr'):
                headers = [td.get_text(strip=True).lower() for td in table.find('tr').find_all('td')]

            first_h = headers[0].lower().strip() if headers else ''
            is_hist_table = first_h in ('anno', 'anno/data')
            is_pb_summary = (any('specialit' in h for h in headers) or any('prestazione' in h for h in headers)) and not is_hist_table

            if is_pb_summary:
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells or len(cells) < 3: continue
                    specialty = cells[0].get_text(strip=True)
                    if not specialty or specialty.lower() in ('gara', 'specialità', 'specialita'): continue
                    pb_data.append({"Specialità": specialty, "Ambiente": cells[1].get_text(strip=True),
                                    "Prestazione": cells[2].get_text(strip=True), "Data": cells[4].get_text(strip=True), 
                                    "Luogo": cells[5].get_text(strip=True)})

            if is_hist_table:
                h_tag = table.find_previous(['h1', 'h2', 'h3', 'h4', 'h5'])
                spec = h_tag.get_text(strip=True) if h_tag else ""
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if len(cells) < 3: continue
                    year_cell = cells[0].get_text(strip=True)
                    if not (year_cell.isdigit() and len(year_cell) == 4): continue
                    date_part = cells[1].get_text(strip=True)
                    perf_cell = cells[6].get_text(strip=True) if len(cells) > 6 else cells[2].get_text(strip=True)
                    full_date = f"{date_part}/{year_cell}" if date_part else year_cell
                    perf_dates[(spec.lower(), perf_cell)] = full_date
                    if year_cell in ['2025', '2026']:
                        sec = hms_to_seconds(perf_cell)
                        if spec and sec < 999999:
                            if spec not in recent_bests or sec < recent_bests[spec][0]:
                                recent_bests[spec] = (sec, perf_cell, cells[-1].get_text(strip=True), year_cell, full_date)

        for pb in pb_data:
            key = (pb.get('Specialità', '').lower(), pb.get('Prestazione', ''))
            if key in perf_dates: pb['Data'] = perf_dates[key]
        return pb_data, recent_bests, last_activity
    except Exception: return [], {}, None

def extract_perf_from_pbs(pbs, distance_keywords, target_year):
    best_perf = None
    best_time_sec = 999999
    best_date = None
    best_loc = None
    best_spec = None
    best_cat = None
    
    for pb in pbs:
        spec_name = pb.get('Specialità', '')
        if any(k.lower() in spec_name.lower() for k in distance_keywords):
            perf = pb.get('Prestazione', '')
            year = pb.get('Data', '').split('/')[-1] if '/' in pb.get('Data', '') else pb.get('Data', '')
            if target_year == "Tutti gli anni (Miglior Risultato Assoluto - PB)" or str(target_year) == year:
                t_sec = hms_to_seconds(perf)
                if t_sec < best_time_sec:
                    best_time_sec = t_sec
                    best_perf = perf
                    best_loc = pb.get('Luogo', '')
                    best_date = pb.get('Data', '')
                    best_spec = spec_name
                    best_cat = "" 
    return best_spec, best_perf, best_date, best_loc, best_cat
