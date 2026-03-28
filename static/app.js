/**
 * app.js — FIDAL Gara Live frontend logic
 */

// ── State ──────────────────────────────────────────────────────────────────
let allAthletes = [];   // [{PETT, COGNOME, NOME, TESSERA, CATEGORIA, SOCIETA, …}]
let currentIdGara = "";

// ── DOM refs ───────────────────────────────────────────────────────────────
const spinner = document.getElementById("spinner");
const modalOverlay = document.getElementById("modal-overlay");
const modalBody = document.getElementById("modal-body");
const modalClose = document.getElementById("modal-close");
const garaBadge = document.getElementById("gara-badge");
const elencoEmpty = document.getElementById("elenco-empty");
const elencoContent = document.getElementById("elenco-content");
const athleteTable = document.getElementById("athlete-table");
const elencoFilter = document.getElementById("elenco-filter");
const elencoCount = document.getElementById("elenco-count");
const cercaResults = document.getElementById("cerca-results");
const icronStatus = document.getElementById("icron-status");
const csvStatus = document.getElementById("csv-status");

// ── Sections ───────────────────────────────────────────────────────────────
const sections = { carica: "section-carica", elenco: "section-elenco", cerca: "section-cerca" };

function showSection(name) {
    Object.keys(sections).forEach(k => {
        document.getElementById(sections[k]).classList.toggle("hidden", k !== name);
        document.getElementById(`nav-${k}`).classList.toggle("active", k === name);
    });
    if (name === "elenco") renderElenco();
    if (name === "cerca") checkCercaState();
}

document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
});

// ── Sorgente radio toggle ──────────────────────────────────────────────────
document.querySelectorAll("input[name='sorgente']").forEach(r => {
    r.addEventListener("change", () => {
        document.getElementById("panel-icron").classList.toggle("hidden", r.value !== "icron");
        document.getElementById("panel-csv").classList.toggle("hidden", r.value !== "csv");
    });
});

// ── Spinner helpers ────────────────────────────────────────────────────────
function showSpinner(msg = "Caricamento…") {
    spinner.querySelector(".spinner-text").textContent = msg;
    spinner.classList.remove("hidden");
}
function hideSpinner() { spinner.classList.add("hidden"); }

// ── Status helpers ─────────────────────────────────────────────────────────
function setStatus(el, msg, type) {
    el.textContent = msg;
    el.className = `status-msg ${type}`;
    el.classList.remove("hidden");
}

// ── Modal ─────────────────────────────────────────────────────────────────
function openModal(html) {
    modalBody.innerHTML = html;
    modalOverlay.classList.remove("hidden");
    document.body.style.overflow = "hidden";
}
function closeModal() {
    modalOverlay.classList.add("hidden");
    document.body.style.overflow = "";
}
modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", e => { if (e.target === modalOverlay) closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// ── Load athletes into state ───────────────────────────────────────────────
function setAthletes(list, idGara, saveToLocal = true) {
    allAthletes = list.map(a => ({
        ...a,
        PETT_NUM: parseInt(a.PETT, 10) || 0,
        NOME_FULL: `${(a.COGNOME || "").trim()} ${(a.NOME || "").trim()}`.trim()
    }));
    allAthletes.sort((a, b) => a.PETT_NUM - b.PETT_NUM);
    currentIdGara = idGara || "";
    updateGaraBadge();

    if (saveToLocal) {
        localStorage.setItem("fidal_id_gara", currentIdGara);
        localStorage.setItem("fidal_iscritti", JSON.stringify(list));
    }
}

function updateGaraBadge() {
    if (currentIdGara) {
        garaBadge.textContent = `Gara ID: ${currentIdGara} · ${allAthletes.length} iscritti`;
        garaBadge.classList.remove("hidden");
    } else {
        garaBadge.classList.add("hidden");
    }
}

// ── Auto-load from LocalStorage on startup ────────────────────────────────
function autoLoadCache() {
    try {
        const id = localStorage.getItem("fidal_id_gara");
        const json = localStorage.getItem("fidal_iscritti");
        if (id && json) {
            const list = JSON.parse(json);
            setAthletes(list, id, false); // don't re-save
            // Pre-fill ICRON input
            document.getElementById("icron-id").value = id;
            setStatus(icronStatus,
                `✅ ${list.length} iscritti caricati dalla sessione locale (ID: ${id})`, "ok");
        }
    } catch (e) { console.warn("Errore caricamento sessione locale:", e); }
}

// ── ICRON fetch ────────────────────────────────────────────────────────────
async function caricaIcron(forceReload = false) {
    const id = document.getElementById("icron-id").value.trim();
    if (!id) { setStatus(icronStatus, "❌ Inserisci un ID gara.", "err"); return; }

    showSpinner("Recupero iscritti da ICRON…");
    try {
        const res = await fetch("/api/carica", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_gara: id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Errore sconosciuto");
        setAthletes(data.iscritti, data.id_gara);
        setStatus(icronStatus, `✅ ${data.count} iscritti caricati — salvati in memoria permanente`, "ok");
        showSection("elenco");
    } catch (e) {
        setStatus(icronStatus, `❌ ${e.message}`, "err");
    } finally {
        hideSpinner();
    }
}

document.getElementById("btn-carica-icron").addEventListener("click", () => caricaIcron(false));
document.getElementById("btn-reload-icron").addEventListener("click", () => caricaIcron(true));

// ── CSV import ────────────────────────────────────────────────────────────
document.getElementById("csv-file").addEventListener("change", async function () {
    const file = this.files[0];
    if (!file) return;
    showSpinner("Lettura CSV…");
    try {
        const text = await file.text();
        const rows = parseCsv(text);
        if (rows.length === 0) throw new Error("Nessuna riga trovata nel CSV.");
        setAthletes(rows, "");
        setStatus(csvStatus, `✅ CSV caricato: ${rows.length} iscritti.`, "ok");
        showSection("elenco");
    } catch (e) {
        setStatus(csvStatus, `❌ ${e.message}`, "err");
    } finally {
        hideSpinner();
    }
});

function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const sep = lines[0].includes(";") ? ";" : ",";
    const rawHeaders = lines[0].split(sep).map(h => h.trim().replace(/^"|"$/g, "").toUpperCase());

    // Column name normalize map
    const norm = {
        PETTORALE: "PETT", BIB: "PETT", TESS: "TESSERA",
        COGN: "COGNOME", NOM: "NOME", SOC: "SOCIETA", CAT: "CATEGORIA"
    };
    const headers = rawHeaders.map(h => {
        for (const [k, v] of Object.entries(norm)) if (h.startsWith(k)) return v;
        return h;
    });

    return lines.slice(1).filter(l => l.trim()).map(l => {
        const vals = l.split(sep).map(v => v.trim().replace(/^"|"$/g, ""));
        const obj = {};
        headers.forEach((h, i) => { obj[h] = vals[i] || ""; });
        if (obj.PETT) obj.PETT = obj.PETT.replace(/\.0$/, "");
        return obj;
    });
}

// ── Elenco rendering ──────────────────────────────────────────────────────
function renderElenco(filter = "") {
    if (allAthletes.length === 0) {
        elencoEmpty.classList.remove("hidden");
        elencoContent.classList.add("hidden");
        return;
    }
    elencoEmpty.classList.add("hidden");
    elencoContent.classList.remove("hidden");

    const q = filter.toLowerCase();
    const filtered = q
        ? allAthletes.filter(a =>
            a.NOME_FULL.toLowerCase().includes(q) ||
            String(a.PETT).includes(q))
        : allAthletes;

    elencoCount.textContent = `${filtered.length} atleti`;

    let html = `<div class="tbl-header">
    <span>Pett.</span><span>Atleta</span><span>Cat.</span><span>Società</span>
  </div>`;
    filtered.forEach(a => {
        html += `<div class="tbl-row" data-pett="${escHtml(a.PETT)}">
      <span class="tbl-pett">${escHtml(String(a.PETT_NUM || a.PETT))}</span>
      <span class="tbl-name">${escHtml(a.NOME_FULL)}</span>
      <span class="tbl-cat">${escHtml(a.CATEGORIA || "")}</span>
      <span class="tbl-soc">${escHtml(a.SOCIETA || "")}</span>
    </div>`;
    });

    athleteTable.innerHTML = html;
    athleteTable.querySelectorAll(".tbl-row").forEach(row => {
        row.addEventListener("click", () => {
            const pett = row.dataset.pett;
            const athlete = allAthletes.find(a => a.PETT === pett);
            if (athlete) openAthleteModal(athlete);
        });
    });
}

elencoFilter.addEventListener("input", () => renderElenco(elencoFilter.value));

// ── Cerca ─────────────────────────────────────────────────────────────────
function checkCercaState() {
    const hasData = allAthletes.length > 0;
    document.getElementById("cerca-empty").classList.toggle("hidden", hasData);
    document.getElementById("cerca-content").classList.toggle("hidden", !hasData);
}

document.getElementById("btn-cerca").addEventListener("click", () => {
    const pett = document.getElementById("search-pett").value.trim();
    const nome = document.getElementById("search-nome").value.trim().toLowerCase();

    let results = [];
    if (pett) {
        results = allAthletes.filter(a => a.PETT === pett);
    } else if (nome) {
        results = allAthletes.filter(a => a.NOME_FULL.toLowerCase().includes(nome));
    }

    if (pett === "" && nome === "") {
        cercaResults.innerHTML = "";
        return;
    }

    if (results.length === 0) {
        cercaResults.innerHTML = `<div class="empty-state">Nessun atleta trovato.</div>`;
        return;
    }

    if (results.length === 1) {
        cercaResults.innerHTML = "";
        openAthleteModal(results[0]);
        return;
    }

    // Multiple results: show sub-table
    let html = `<div class="tbl-header" style="grid-template-columns:70px 1fr 90px">
    <span>Pett.</span><span>Atleta</span><span>Cat.</span>
  </div>`;
    results.forEach(a => {
        html += `<div class="tbl-row" data-pett="${escHtml(a.PETT)}"
                  style="grid-template-columns:70px 1fr 90px">
      <span class="tbl-pett">${escHtml(String(a.PETT_NUM || a.PETT))}</span>
      <span class="tbl-name">${escHtml(a.NOME_FULL)}</span>
      <span class="tbl-cat">${escHtml(a.CATEGORIA || "")}</span>
    </div>`;
    });
    cercaResults.innerHTML = html;
    cercaResults.querySelectorAll(".tbl-row").forEach(row => {
        row.addEventListener("click", () => {
            const athlete = allAthletes.find(a => a.PETT === row.dataset.pett);
            if (athlete) openAthleteModal(athlete);
        });
    });
});

// also trigger on Enter
["search-pett", "search-nome"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
        if (e.key === "Enter") document.getElementById("btn-cerca").click();
    });
});

// ── Athlete modal ─────────────────────────────────────────────────────────
async function openAthleteModal(athlete) {
    const tessera = (athlete.TESSERA || "").trim();
    const nomeFull = athlete.NOME_FULL;
    const pett = athlete.PETT_NUM || athlete.PETT;
    const cat = athlete.CATEGORIA || "";
    const soc = athlete.SOCIETA || "";

    // Show skeleton card immediately
    openModal(renderSkeleton(nomeFull, pett, cat, soc));

    if (!tessera) {
        modalBody.innerHTML = renderSkeleton(nomeFull, pett, cat, soc) +
            `<p style="color:#f85149;margin-top:1rem">⚠️ Tessera non disponibile per questo atleta.</p>`;
        return;
    }

    try {
        const res = await fetch(`/api/pb/${encodeURIComponent(tessera)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Errore server");
        modalBody.innerHTML = renderCommentaryCard(nomeFull, pett, cat, soc, data);
    } catch (e) {
        modalBody.innerHTML = renderSkeleton(nomeFull, pett, cat, soc) +
            `<p style="color:#f85149;margin-top:1rem">❌ ${e.message}</p>`;
    }
}

function renderSkeleton(name, pett, cat, soc) {
    return `
    <div class="commentary-meta">Pettorale #${escHtml(String(pett))} &nbsp;·&nbsp; ${escHtml(cat)}</div>
    <div class="commentary-name">${escHtml(name)}</div>
    <div style="color:#8b949e;font-size:0.85rem;margin-bottom:1rem">${escHtml(soc)}</div>
    <div style="color:#8b949e;font-style:italic">⏳ Recupero primati da FIDAL…</div>`;
}

function renderCommentaryCard(name, pett, cat, soc, data) {
    const road = data.road || [];
    const other = data.other || [];

    let roadHtml = "";
    road.forEach(pb => {
        const rec = pb.recente;
        const recBadge = rec
            ? `<span class="pb-road-recent">⭐ ${escHtml(rec.perf)} @ ${escHtml(rec.luogo)} (${escHtml(rec.anno)})</span>`
            : "";
        const luogoTag = pb.Luogo
            ? `<span class="pb-road-loc">📍 ${escHtml(pb.Luogo)}</span>`
            : "";
        roadHtml += `
      <div class="pb-road-row">
        <span class="pb-road-spec">${escHtml(pb["Specialità"])}${luogoTag}</span>
        <span class="pb-road-perf">${escHtml(pb.Prestazione)}${recBadge}</span>
      </div>`;
    });

    let otherHtml = "";
    other.slice(0, 8).forEach(pb => {
        otherHtml += `
      <div class="pb-other-row">
        <span class="pb-other-spec">${escHtml(pb["Specialità"])}</span>
        <span class="pb-other-perf">${escHtml(pb.Prestazione)}</span>
      </div>`;
    });

    const noRoad = `<div style="color:#888;font-style:italic;font-size:0.9rem">Nessun record su strada registrato</div>`;

    return `
    <div class="commentary-meta">Pettorale #${escHtml(String(pett))} &nbsp;·&nbsp; ${escHtml(cat)}</div>
    <div class="commentary-name">${escHtml(name)}</div>
    <div style="color:#8b949e;font-size:0.85rem;margin-bottom:1.4rem">${escHtml(soc)}</div>
    <div class="commentary-section-title">🏃 Strada / Maratona</div>
    ${roadHtml || noRoad}
    ${otherHtml ? `
      <div class="pb-other-section">Altri Primati</div>
      <div class="pb-other-grid">${otherHtml}</div>
    ` : ""}
    ${data.total === 0 ? `<p style="color:#8b949e;margin-top:1rem;font-style:italic">Nessun primato registrato su FIDAL.</p>` : ""}`;
}

// ── Utils ─────────────────────────────────────────────────────────────────
function escHtml(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ── Init ──────────────────────────────────────────────────────────────────
autoLoadCache();
