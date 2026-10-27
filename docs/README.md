# Documentazione Unical Support

Documentazione consolidata al 28 ottobre 2026, basata sul codice corrente.

| Documento | Contenuto |
| --- | --- |
| [ARCHITECTURE](ARCHITECTURE.md) | Componenti, dati, flussi AI, contratti e interfaccia |
| [OPERATIONS](OPERATIONS.md) | Avvio locale, account, posta, monitoraggio e diagnosi |
| [DEPLOY](DEPLOY.md) | Aggiornamento remoto via jump host, build, backup e riavvio |
| [MIGRATIONS](MIGRATIONS.md) | Revisioni Alembic, verifiche, generazione e rollback |
| [Anteprima email](assets/email-preview.html) | Esempio statico del template istituzionale |

I precedenti report per singola funzionalità sono stati consolidati in questi documenti: le vecchie indicazioni su template precompilati, importazione web, filtri locali e limiti della lista email non descrivevano più l'applicazione attuale. Gli script Alembic in `alembic/versions/` restano la fonte eseguibile per ogni modifica dello schema.

Per aggiornare il server partire da [DEPLOY](DEPLOY.md). La verifica SSH della sessione non è stata completata e non è stato eseguito alcun deploy remoto: lo stato della VPS va rilevato con `scripts/deploy.py --check` dopo aver verificato l'accesso.
