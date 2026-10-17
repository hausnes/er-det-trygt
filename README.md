# 'Er det trygt?'

> Du står og ser på ei rute ned frå ein fjelltopp, og lurar på: "Er det trygt å gå ned her?"

Eg har mange gonger opplevd å stå på eit punkt under ein fjelltur, og lure på om det er mogleg å gå ned ei viss rute - eller å sjå alternativ som er betre enn andre. 

NB: Denne tjenesten kan ikkje garantere deg ei trygg rute, men kan gje deg større sjanse for å velgje riktig.

Tjenesten treng GPS-tilgang frå mobilen din, og deretter markerer du kvar du skal ende opp, for så at tjenesten gjer deg gode alternativ.
## Slik fungerer det (første versjon)

1. Du vel startpunkt (trykk på kartet, eller bruk GPS-posisjonen) og målpunkt. Begge kan flyttast ved å dra dei.
2. Backend-en hentar terrengmodell (DTM) frå [Kartverket sine høgdedata](https://hoydedata.no) for området.
3. Hellinga blir rekna ut for kvar celle. Terreng over 45° (og cellene rett ved sida) blir rekna som ufarbart, og bratt terreng kostar meir enn slakt.
4. Innsjøar, tjørner og breie elvar frå Kartverket sitt N50-kart blir rekna som ufarbare, slik at ruta går rundt dei. Ruta kan likevel krysse bekkar og smale elvar, sidan dei berre er teikna som liner i N50.
5. Ruta med lågast samla kostnad blir funnen og vist på kartet, farga etter kor bratt det er.
6. Med «Følg ruta» brukar appen GPS-en til å stadfeste at du er på ruta (innanfor 30 m), og kor langt det er att. Går du utanfor, får du ei åtvaring (og vibrasjon på Android). Er GPS-signalet for unøyaktig, seier appen ifrå i staden for å stadfeste.

Avgrensingar: Høgdemodellen kjenner ikkje til snø, is, bre eller lausmassar. Vatn blir alltid unngått, også om vinteren når det kan vere islagt. «Følg ruta» fungerer berre når skjermen er på og appen er open, sidan nettlesarar ikkje får GPS-posisjon i bakgrunnen. Maks avstand mellom punkta er 15 km. Lange ruter blir rekna ut med grovare rutenett (opptil ~15 m), og då kan små stup forsvinne.

## Utvikling

Krev Python 3.12+ og Node 20+.

```sh
# Backend (FastAPI) – http://localhost:8000
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# Testar
.venv/bin/python -m pytest

# Frontend (Vite + TypeScript + MapLibre) – http://localhost:5173
cd frontend
npm install
npm run dev
npm test
```

GPS-posisjon i nettlesaren krev HTTPS (eller `localhost`). For å teste på mobil kan du t.d. bruke ein tunnel som `cloudflared` eller `ngrok`.

## Datakjelder

- Høgdedata, vassdata (N50) og topografisk kart: © Kartverket (CC BY 4.0)
