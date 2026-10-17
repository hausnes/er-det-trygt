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
.venv/bin/pip install -r requirements-dev.txt
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

## Hosting med Docker (t.d. på NAS)

Alt køyrer i éin container: backend-en serverer òg den ferdigbygde frontend-en på port 8000.
Imaget fungerer på både Intel/AMD- og ARM-prosessorar.

Ved kvar push til `main` køyrer GitHub Actions testane og publiserer imaget til
`ghcr.io/hausnes/er-det-trygt:latest`. Første gong må pakken gjerast offentleg
(GitHub → profil → Packages → er-det-trygt → Package settings → Change visibility),
elles må NAS-en logge inn på ghcr.io.

På NAS-en:

- **Synology:** Container Manager → Prosjekt → Opprett, og lim inn `compose.yaml`.
- **Ugreen:** Docker → Prosjekt/Compose → Opprett, og lim inn `compose.yaml`.

Tenesta svarar då på `http://<nas-ip>:8000`. Oppdater ved å hente nytt image og starte prosjektet på nytt.

Bygge og køyre lokalt:

```sh
docker build -t er-det-trygt .
docker run --rm -p 8000:8000 er-det-trygt
```

### HTTPS (nødvendig for GPS på mobil)

Nettlesarar gjev berre GPS-posisjon til sider med HTTPS. To alternativ:

- **Berre for deg sjølv:** [Tailscale](https://tailscale.com) på NAS-en og mobilen. `tailscale serve` gjev ei HTTPS-adresse
  som berre dine einingar når, utan å opne portar i ruteren.
- **Offentleg tilgjengeleg:** reverse proxy med Let's Encrypt-sertifikat foran port 8000. På Synology finst dette
  innebygd (Kontrollpanel → Påloggingsportal → Avansert → Omvendt proxy, og Sikkerheit → Sertifikat).
  Opne berre port 443 (proxyen) i ruteren, ikkje port 8000. Tenesta stoler på `X-Forwarded-For` frå proxyen
  for å finne brukaren si IP-adresse, så direkte tilgang til port 8000 ville gjort det mogleg å omgå grensene under.

### Grenser

For å verne NAS-en og Kartverket sine tenester er det grenser for rutesøk, som kan endrast i `compose.yaml`:

- 10 søk per minutt og 60 per time for kvar IP-adresse (svarar med HTTP 429 og ei melding på nynorsk).
- Maks 3 ruteberekningar samtidig. Andre ventar i kø i opptil 30 sekund før dei får beskjed om at tenesta er travel.

## Datakjelder

- Høgdedata, vassdata (N50) og topografisk kart: © Kartverket (CC BY 4.0)
