# Creare il database `tosca_registry` su Azure

**Non serve creare un nuovo server PostgreSQL.** Il server esiste già: è quello che ospita
`suncity`, `sunexp3` e `sunbookingdb`. Va aggiunto un **database** dentro quel server.

È la stessa differenza che c'è fra comprare un altro armadio e aggiungere un cassetto a quello
che hai. Conseguenze pratiche:

- **costo aggiuntivo: zero** — su PostgreSQL Flexible Server si paga il server (la SKU B1ms), non
  il numero di database;
- **niente da configurare in rete** — regole firewall, VNet e SSL sono quelle del server, già a
  posto perché ci si connette già;
- **stesso host, stessa porta** nella stringa di connessione: cambia solo il nome del database in
  fondo.

Ci sono due strade. Scegline **una**.

---

## Strada A — dal portale Azure (nessun comando)

1. [portal.azure.com](https://portal.azure.com) → cerca **"Azure Database for PostgreSQL"**
2. apri il tuo server (quello con SKU **B1ms**)
3. nel menu di sinistra: **Impostazioni → Database** *(in inglese: Settings → Databases)*
4. pulsante **+ Aggiungi** / **+ Add**
5. **Nome**: `tosca_registry`
6. **Charset**: `UTF8` — **Collation**: lascia quella proposta di default
7. **Salva**

Il database nasce già di proprietà del tuo utente: non serve altro sul portale.

---

## Utente

**Nessun utente nuovo.** Si usa lo stesso con cui accedi già a `suncity`, `sunexp3` e
`sunbookingdb`: il database creato dal portale appartiene di suo a quell'utente, quindi non serve
alcun `ALTER` di proprietà.

---

## Dopo

1. `01A_utente_e_proprieta.sql` — un controllo di due righe che sei nel database giusto e che
   puoi scrivere
2. `02_tabelle_registry.sql` — le 8 tabelle
3. riga nel `.env`, identica alle altre con il solo nome del database cambiato in fondo:

```
REGISTRY_DATABASE_URI=postgresql://<utente>:<password>@<host>:5432/tosca_registry?sslmode=require
```

**Il nome della variabile non è negoziabile:** deve *non* corrispondere al pattern
`SQLALCHEMY_DATABASE_URI<numero>`, perché `collect_db_pool()` in `wsgi.py` monta come tenant
tutto ciò che gli assomiglia. Un registro montato come negozio sarebbe un guaio.
