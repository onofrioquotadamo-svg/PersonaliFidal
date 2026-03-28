"""
server.py — Flask REST API for FIDAL Race Registrant Lookup
Run: python server.py
"""

import os
import json
from flask import Flask, jsonify, request, send_from_directory
from fidal_core import (
    fetch_from_icron,
    encode_tessera,
    extract_all_pbs,
    is_road_event,
    get_recent_best,
)

app = Flask(__name__, static_folder="static", static_url_path="")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/carica", methods=["POST"])
def carica():
    """Fetch athletes from ICRON, returns them to the caller. Stateless."""
    data = request.get_json(force=True)
    id_gara = str(data.get("id_gara", "")).strip()
    if not id_gara:
        return jsonify({"error": "id_gara mancante"}), 400

    try:
        athletes = fetch_from_icron(id_gara)
        return jsonify({
            "id_gara": id_gara,
            "iscritti": athletes,
            "count": len(athletes)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pb/<tessera>", methods=["GET"])
def get_pb(tessera: str):
    """Scrape PBs from FIDAL for a given tessera number."""
    tessera = tessera.strip()
    if not tessera:
        return jsonify({"error": "tessera mancante"}), 400

    try:
        slug = encode_tessera(tessera)
        url = f"https://www.fidal.it/atleta/x/{slug}"
        pbs, recent_bests = extract_all_pbs(url)

        road = []
        other = []
        for pb in pbs:
            spec = pb["Specialità"]
            recent = get_recent_best(spec, recent_bests)
            entry = {**pb, "is_road": is_road_event(spec), "recente": recent}
            if is_road_event(spec):
                road.append(entry)
            else:
                other.append(entry)

        return jsonify({
            "tessera": tessera,
            "fidal_url": url,
            "road": road,
            "other": other,
            "total": len(pbs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Get port from environment variable, default to 5000 if not set (Cloud deployment)
    port = int(os.environ.get("PORT", 5000))
    print(f"FIDAL Webapp avviata su http://0.0.0.0:{port}")
    # Disable debug and reloader for safer cloud execution
    app.run(debug=False, host="0.0.0.0", port=port, use_reloader=False)
