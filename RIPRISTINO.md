# Ripristino dei dati — le tre reti, in ordine di comodità

Aggiornato: 17/08/2026 · Riassunto anche nel pannello owner, pulsante **🛟 Info backup**

Prima di leggere: **quasi sempre la risposta è la rete 1.** Le altre servono in
scenari via via più gravi e più rari.

---

## Regola operativa, in una riga

> **PITR per i disastri. LTR per il singolo cliente.**

È la conseguenza di un fatto che a 100 tenant diventa decisivo: il PITR ripristina
**tutto il server**, l'LTR ha **un dump per database**. Recuperare un solo negozio
dal PITR significherebbe far nascere un server temporaneo con dentro i dati di
tutti e 100, mentre dall'LTR si scarica e si reimporta solo quello che serve.

C'è anche una ragione contrattuale, non solo di comodità: l'**art. 17.4** promette
che *«il ripristino richiesto da un cliente non comporta in alcun caso accesso ai
dati di altri clienti»*. Con l'LTR quella promessa si mantiene senza discussioni.

---

## Rete 1 — PITR (35 giorni, qualsiasi istante)

**Quando:** cancellazione per errore, deploy sbagliato, corruzione, guasto del server.
È il caso normale.

**Cosa fa:** ricrea un **server nuovo** allo stato esatto di un istante scelto.

**Come:** portale → server `sunbooking` → *Panoramica* → **Ripristina** → scegli data e ora.

⚠️ **Il ripristino è di tutto il server, non di un singolo database.** Per recuperare
un solo negozio: ripristini su un server temporaneo, estrai il database che ti serve,
lo reimporti in produzione, poi elimini il server temporaneo.

---

## Rete 2 — Vault `Tosca-backup` (settimanale, 12 mesi)

**Quando:** ti serve qualcosa più vecchio di 35 giorni.

**Cosa fa:** backup logici con `pg_dump`, ripristinati **come file** su uno storage
account, da cui reimporti dove vuoi.

**Come:** portale → `Tosca-backup` → *Istanze di backup* → `sunbooking` → **Ripristina**
→ scegli il punto di ripristino → destinazione: storage account.

Vive **fuori dalla tua sottoscrizione**, quindi resiste anche alla cancellazione
accidentale delle risorse.

### Configurazione in essere (17/08/2026)

| | |
|---|---|
| Vault | `Tosca-backup` — ridondanza **di zona** (tre datacenter di Italy North) |
| Criterio | `settimanale-12mesi` — domenica, ritenzione **12 mesi** |
| Immutabilità | attiva, **non bloccata** |
| Eliminazione temporanea | attiva, 14 giorni |
| Ripristino tra sottoscrizioni | abilitato |

Il vault precedente `sunbooking-backup` (ridondanza **locale**, ritenzione 10 anni)
è stato dismesso. Restava da eliminare quando il cestino dell'eliminazione
temporanea si sarà svuotato, un paio di settimane dopo il 17/08/2026.

⚠️ **La ridondanza di un vault si sceglie alla creazione e non si cambia più.**
Per passare da locale a zona è stato necessario creare un vault nuovo, eliminare
l'istanza dal vecchio e riconfigurare. Un'operazione che richiede di disattivare
temporaneamente l'immutabilità: da mettere in conto se un giorno servisse rifarla.

⚠️ **In Italy North la ridondanza geografica non esiste**, né per il vault né per
il server: è una regione **senza regione accoppiata**, progettata con tre zone di
disponibilità al posto della coppia. Non è una dimenticanza di configurazione, e
nessuna migrazione la otterrebbe restando in quella regione.

---

## Rete 3 — Backup esterno fuori da Azure ❌ SCARTATA

**Decisione del 17/08/2026: non si fa.**

Coprirebbe solo la distruzione definitiva di tutte e tre le zone di Italy North —
sproporzionato rispetto alla dimensione attuale. E appoggiare una rete di sicurezza
al piano gratuito di un fornitore terzo introduce una dipendenza che può cambiare
condizioni da un giorno all'altro.

Il codice è stato scritto e poi **rimosso**: non è rimasto nulla in produzione.

**Quando rimettere in discussione la scelta:** quando ci saranno clienti paganti.
A quel punto il rischio non è più solo tuo, e il fornitore lo si sceglie a pagamento.

Il ripristino avverrebbe da CSV, ricreando lo schema con `db.create_all()` (negozi)
o con `registry/02_tabelle_registry.sql` (registro) e ricaricando i dati. Non serve
documentarlo finché la rete non è attiva.

---

## Da fare almeno una volta, prima che serva

**Provare un ripristino per davvero**, dalla rete 2: ripristinare come file su uno
storage account, reimportare un database in un server di prova, contare le righe e
confrontarle con l'originale.

E **cronometrare**. Quel numero serve per rispondere a una cliente in panico senza
inventare, e per sapere quanto dura davvero un disservizio.

Un backup mai ripristinato non è un backup, è una speranza.
