# 🚀 FIDAL Gara Live — Guida al Deploy (Cloud)

Questa guida ti spiega come mettere online la tua webapp in modo che chiunque possa usarla tramite un link pubblico (es. `https://fidal-live.onrender.com`).

## 1. Carica il codice su GitHub
Il modo più semplice per fare il deploy è collegare un repository GitHub.
1. Crea un nuovo repository su [GitHub](https://github.com/new).
2. Carica tutti i file contenuti in questa cartella (`fidal_webapp`).

## 2. Deploy su Render.com (Gratis/Semplice)
1. Vai su [Render.com](https://render.com/) e crea un account.
2. Clicca su **New +** e seleziona **Web Service**.
3. Collega il tuo account GitHub e seleziona il repository appena creato.
4. Configura così:
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app` (Già impostato nel Procfile)
5. Clicca su **Create Web Service**.

## 3. Deploy su Railway.app (Alternativa)
1. Vai su [Railway.app](https://railway.app/).
2. Clicca su **New Project** -> **Deploy from GitHub repo**.
3. Seleziona il repository.
4. Railway rileverà automaticamente il `Procfile` e avvierà l'app.

---

### 📝 Note Tecniche
- **Porta**: L'app è configurata per leggere la variabile d'ambiente `PORT` fornita dal Cloud.
- **Persistenza**: Se usi il piano gratuito di Render, i dati caricati (cache) potrebbero azzerarsi al riavvio del server. Tuttavia, l'app continuerà a funzionare caricando i dati freschi da ICRON/FIDAL ogni volta.
