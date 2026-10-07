# ro-etoll Monitorizarea rovinietelor în Home Assistant, prin portalul CNAIR eToll.

<img src="custom_components/ro_etoll/brand/icon.png" alt="Pictograma ro-etoll" width="88" />

**Monitorizarea rovinietelor în Home Assistant, prin portalul CNAIR eToll.**

Verifică valabilitatea rovinietei, data expirării și numărul de zile rămase,
consultă totalurile facturilor și creează notificări de reînnoire direct din
Home Assistant.

**Întreținut de:** [Kosztyk](https://github.com/Kosztyk) ·
**Versiune:** `3.0.0-beta.4` ·
**Proiect pe GitHub:** [Kosztyk/ro-etoll](https://github.com/Kosztyk/ro-etoll)

> Integrarea este în versiune beta. Soldul peajelor și istoricul trecerilor depind
> de datele furnizate de eToll. Dacă serviciul răspunde cu `UNAVAILABLE`, senzorii
> respectivi rămân indisponibili. Monitorizarea rovinietei continuă independent.

## Funcționalități

- Verificarea valabilității rovinietei pentru vehiculele înregistrate în profilul eToll curent.
- Senzori pentru data expirării și numărul de zile rămase, utilizabili în panouri și automatizări.
- Numărul facturilor, valoarea lor totală și informații despre cont.
- Verificarea peajelor printr-o metodă alternativă atunci când verificarea vehiculului salvat este indisponibilă.
- Detectarea automată a vehiculelor nou înregistrate, la actualizările ulterioare.
- Interval de actualizare și perioadă a istoricului facturilor configurabile.
- Configurare din interfață, modificarea datelor de autentificare și reautentificare.
- Diagnosticare fără identificatorii contului și ai vehiculelor în datele de diagnostic proprii integrării.
- Pictograme și siglă incluse, fără cheie de activare, perioadă de probă sau serviciu extern de verificare a licenței.

Integrarea este destinată monitorizării. Nu plasează comenzi, nu efectuează plăți,
nu înregistrează sau modifică vehicule și nu schimbă setările profilului.

## Cerințe

- **Home Assistant 2025.11 sau mai nou.**
- Un cont pe [portal.etoll.ro](https://portal.etoll.ro/portal-extern/) care permite
  autentificarea cu adresă de e-mail sau nume de utilizator și parolă.
- Cont verificat, un profil curent selectat și vehiculele înregistrate în portalul oficial.

Această versiune nu acceptă conturile care se autentifică exclusiv prin ROeID
și nici autentificarea interactivă cu mai mulți factori (MFA).
Pentru afișarea pictogramelor și a siglei incluse este necesar
**Home Assistant 2026.3 sau mai nou**; consultă
[documentația Home Assistant despre imaginile integrărilor](https://developers.home-assistant.io/docs/core/integration/brand_images/).

## Instalare

### Prin HACS, ca depozit personalizat

După publicarea proiectului pe GitHub:

1. Deschide **HACS → ⋮ → Depozite personalizate** (`Custom repositories`).
2. Introdu `https://github.com/Kosztyk/ro-etoll` și selectează tipul **Integrare** (`Integration`).
3. Adaugă depozitul, apoi descarcă **ro-etoll** din HACS.
4. Repornește Home Assistant.
5. Deschide **Setări → Dispozitive și servicii → Adaugă integrare** și caută **ro-etoll**.
6. Introdu datele contului eToll și alege setările de actualizare.

Instalarea folosește [funcția HACS pentru depozite personalizate](https://www.hacs.xyz/docs/faq/custom_repositories/).
Proiectul nu trebuie să fie inclus în catalogul implicit HACS.

### Instalare manuală

1. Descarcă și dezarhivează arhiva cu sursele proiectului.
2. Copiază întregul folder `custom_components/ro_etoll` în directorul de configurare
   Home Assistant, astfel încât fișierul manifest să se afle la
   `/config/custom_components/ro_etoll/manifest.json`.
3. Include și subfolderele `brand/` și `translations/`.
4. Repornește Home Assistant și adaugă **ro-etoll** din **Dispozitive și servicii**.

Dacă arhiva ZIP conține doar componenta, extrage conținutul direct în
`/config/custom_components/ro_etoll`.

Numele afișat și numele proiectului sunt **ro-etoll**. Domeniul Home Assistant și
folderul componentei sunt **`ro_etoll`**. Păstrează caracterul `_` în numele
folderului de instalare.

## Senzori disponibili

Senzorii asociați unui vehicul includ numărul de înmatriculare în numele afișat.

| Senzor | Valoare | Detalii |
| --- | --- | --- |
| **Date utilizator** | Numele profilului | ID-ul profilului și adresa de e-mail sunt disponibile ca atribute. |
| **Rovinietă activă** | `Da` / `Nu` | Valabilitatea curentă, obținută prin verificare; dacă lipsesc datele, senzorul rămâne indisponibil. |
| **Expirare rovinietă** | Data și ora expirării | Expirarea rovinietei selectate; sursa datelor apare în atribute. |
| **Zile până la expirare rovinietă** | Zile | Numărul de intervale complete de 24 de ore rămase; poate fi zero în ziua expirării sau negativ după expirare. |
| **Raport tranzacții** | Numărul facturilor | Valoarea totală a facturilor în RON și perioada selectată sunt disponibile ca atribute. |
| **Sold peaje neexpirate** | Treceri rămase | Reprezintă un număr de treceri, nu o sumă de bani; necesită date valide despre peaje. |
| **Treceri pod** | Numărul trecerilor | Numără trecerile returnate de verificarea peajelor; detaliile recente apar în atribute. |
| **Stare verificare peaje** | Stare de diagnostic | Explică dacă datele despre peaje sunt disponibile, indisponibile, incomplete sau dacă verificarea a eșuat. |
| **Restanțe treceri pod** | `Nesuportat de API` | Senzor de diagnostic dezactivat implicit; detectarea trecerilor neachitate nu este disponibilă în prezent. |

Senzorii de expirare folosesc cu prioritate datele obținute prin verificare.
Atunci când este posibil, pot utiliza data explicită de expirare a rovinietei
curente din informațiile de eligibilitate ale vehiculului. Atributul
**Sursă dată expirare** indică folosirea acestei surse alternative.
Existența unei date de expirare nu confirmă, singură, că rovinieta este activă.

## Configurare

| Setare | Valoare implicită | Interval permis |
| --- | --- | --- |
| Interval de actualizare | 3.600 de secunde / 1 oră | 300–86.400 de secunde |
| Istoric facturi | 2 ani | 1–10 ani |

Modifică aceste setări din opțiunile integrării. Folosește **Reconfigurează**
pentru a actualiza datele de autentificare. Perioada istoricului stabilește ce
facturi sunt incluse în raport; nu reprezintă un istoric al trecerilor neachitate.

## Notificări pentru expirarea rovinietei

Folosește direct senzorul **Zile până la expirare rovinietă** într-un declanșator
bazat pe starea numerică (`numeric_state`). Lasă câmpul **Atribut** necompletat.
Starea `Da`/`Nu` a senzorului de rovinietă activă nu este numerică.

[Exemplul de automatizare inclus](examples/automation_rovinieta.yaml) trimite o
notificare persistentă în Home Assistant când mai sunt mai puțin de 15 zile până
la expirare și un memento zilnic la ora 09:00. Exemplul exclude rovinietele expirate
și valorile necunoscute sau indisponibile. Înlocuiește fiecare ID de entitate din
exemplu cu ID-ul real din instalarea ta.

Cu denumirea implicită, numărul de test `B123TST` produce o entitate precum
`sensor.ro_etoll_zile_pana_la_expirare_rovinieta_b123tst`.
Home Assistant poate păstra un ID redenumit sau poate adăuga un sufix, așadar
verifică ID-ul în **Instrumente pentru dezvoltatori → Stări**.

## Disponibilitatea datelor despre peaje

Verificarea peajelor este efectuată separat de verificarea rovinietei. Dacă
verificarea prin ID-ul vehiculului salvat returnează `UNAVAILABLE`, integrarea
încearcă o singură verificare alternativă, folosind numărul de înmatriculare,
țara și seria de șasiu (VIN), atunci când aceasta este disponibilă. Datele obținute
prin metoda alternativă sunt acceptate numai dacă identifică același vehicul.

Dacă ambele metode returnează `UNAVAILABLE`, nu există un sold curent sau un număr
de treceri care să poată fi afișat. Un rezultat indisponibil nu este transformat
în zero. Un răspuns valid care indică explicit lipsa trecerilor poate produce
valoarea zero.

Deschide **Stare verificare peaje** pentru a consulta:

- **Cod stare verificare** — rezultatul curent al verificării peajelor.
- **Metodă verificare** — verificare prin ID-ul vehiculului salvat sau prin numărul de înmatriculare.
- **Cod verificare alternativă** — rezultatul metodei alternative, dacă a fost încercată.
- **Cod HTTP verificare alternativă** — codul unei erori HTTP, dacă este cazul.

Senzorul **Restanțe treceri pod** poate rămâne dezactivat. Starea sa de funcție
nesuportată nu indică dacă vehiculul are treceri neachitate. Nici o listă goală de
facturi, nici istoricul achizițiilor nu confirmă absența trecerilor neachitate.

## Actualizare și migrare

**Dacă folosești deja `ro_etoll`:** înlocuiește întregul folder al componentei,
repornește Home Assistant și păstrează configurația existentă a integrării.
ID-urile entităților înregistrate se păstrează. Reîncarcă pagina sau aplicația
pentru a vedea pictogramele actualizate.

**Dacă treci de la `erovinieta`:** dezactivează vechea integrare, instalează
`ro_etoll`, repornește Home Assistant și adaugă o nouă integrare **ro-etoll**.
Actualizează panourile și automatizările pentru a folosi noile entități.
Redenumirea folderului nu transferă automat configurația între domenii.

Consultă [MIGRATION.md](MIGRATION.md) pentru procedura completă și instrucțiunile
de revenire la versiunea anterioară.

## Depanare

| Problemă | Ce poți verifica |
| --- | --- |
| Autentificarea eșuează | Verifică dacă te poți conecta în portal și dacă ai contul verificat; verifică dacă este necesară o metodă de autentificare interactivă nesuportată. |
| Nu apar vehicule | Verifică dacă vehiculele sunt înregistrate în profilul curent din portal. |
| Senzorii pentru peaje sunt indisponibili | Consultă **Stare verificare peaje** și compară rezultatul cu verificarea peajelor din portal. |
| Raportul de facturi afișează zero | Verifică profilul curent și perioada selectată; raportul include doar facturile returnate de eToll. |
| Automatizarea raportează o entitate necunoscută | Înlocuiește referințele vechi `sensor.erovinieta_...` cu ID-urile reale ale noilor entități. |
| Pictograma nu apare | Folosește HA 2026.3 sau mai nou, copiază întregul folder `brand/`, repornește HA și reîncarcă pagina sau aplicația. |

Când raportezi o problemă, include versiunea integrării, versiunea Home Assistant,
liniile relevante din jurnal și fișierul obținut prin **Descarcă datele de diagnosticare**
al integrării. Nu publica parole, tokenuri sau capturi HAR brute în sesizările publice.

[Raportează o problemă](https://github.com/Kosztyk/ro-etoll/issues) ·
[Întrebări frecvente](FAQ.md) · [Ghid de depanare](DEBUG.md)

## Funcționalități propuse

Următoarele idei sunt destinate versiunilor viitoare și **nu sunt implementate în beta.4**.
Răspunsurile noilor puncte de acces API și semnificația câmpurilor trebuie verificate
înainte de activarea acestor funcții.

| Propunere | Sursa datelor | Utilitate |
| --- | --- | --- |
| Totalul facturilor pe lună și pe an | `/api/invoices` | Senzori numerici în RON pentru grafice și evidența cheltuielilor. |
| Valoarea ultimei facturi și data plății | `/api/invoices` | Afișarea celei mai recente plăți înregistrate și a valorii facturii asociate. |
| Numărul notificărilor și ultima notificare | `/api/notifications/summary`, `/api/notifications` | Afișarea mesajelor din portal și declanșarea alertelor în HA; semnificația stării de notificare necitită trebuie încă verificată. |
| Rovinietă care expiră curând | Datele de expirare existente | Un senzor binar cu prag de avertizare configurabil. |
| Data de început a următoarei roviniete | `/api/tolls/verification` | Afișarea unei roviniete viitoare, atunci când răspunsul include una. |
| Numărul serviciilor cumpărate și ultima achiziție | `/api/tolls` | Monitorizarea produselor returnate pentru profilul curent, cu tipul, prețul și datele aferente ca atribute. |
| Numărul vehiculelor înregistrate | `/api/vehicles` | Monitorizarea numărului de vehicule din lista interogată. |
| Ultima actualizare reușită pentru fiecare sursă | Rezultatele coordonatorului de actualizare | Indicarea separată a actualizării datelor despre rovinietă și a disponibilității datelor despre peaje. |

Stările comenzilor, estimarea costului de reînnoire și statisticile călătoriilor
sau sesiunilor cu tarifare pe kilometru necesită verificări suplimentare ale
structurii răspunsurilor API și ale datelor disponibile în cont. Resursele geografice
și imaginile hărților sunt date auxiliare; un punct de acces pentru geocodare nu
oferă urmărirea vehiculului în timp real. Indicatorii de activare a funcțiilor
(`feature flags`) descriu configurația și nu confirmă funcționarea serviciului.

## Dezvoltare și informații despre proiect

Suita de teste automate pentru beta.4 a trecut **97 de teste**, care acoperă
autentificarea, paginarea, interpretarea răspunsurilor, verificarea alternativă a
peajelor, valorile senzorilor, confidențialitatea datelor de diagnostic și blocarea
operațiunilor interzise care ar modifica datele contului. Consultă [TESTING.md](TESTING.md)
pentru mediul de testare, constatările din diagnosticarea unei instalări reale și
comenzile de reproducere a testelor.

Integrarea folosește un API al portalului care nu are documentație publică și poate
necesita actualizări atunci când portalul se modifică. Consultă [API_NOTES.md](API_NOTES.md)
pentru structurile API analizate, [BRANDING.md](BRANDING.md) pentru detalii despre
pictograme și siglă, respectiv [ORIGIN.md](ORIGIN.md) pentru istoricul proiectului.

Întreținut de **Kosztyk**. Acesta este un proiect comunitar pentru Home Assistant.
