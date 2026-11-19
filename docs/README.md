# Documentazione Unical Support

Documentazione consolidata, aggiornata al 18 novembre 2026 e basata sul codice corrente.

| Documento | Contenuto |
| --- | --- |
| [ARCHITECTURE](ARCHITECTURE.md) | Componenti, dati, flussi AI, contratti e interfaccia |
| [OPERATIONS](OPERATIONS.md) | Avvio locale, account, posta, monitoraggio e diagnosi |
| [DEPLOY](DEPLOY.md) | Aggiornamento remoto via jump host, build, backup e riavvio |
| [MIGRATIONS](MIGRATIONS.md) | Revisioni Alembic, verifiche, generazione e rollback |
| [OBSERVABILITY](OBSERVABILITY.md) | Langfuse interno, conteggio token e storico delle fonti |
| [EMAIL_CLEANUP](EMAIL_CLEANUP.md) | Cancellazione manuale delle email dal database, con backup e transazione |
| [Anteprima email](assets/email-preview.html) | Esempio statico del template istituzionale |

I precedenti report per singola funzionalità sono stati consolidati in questi documenti: le vecchie indicazioni su template precompilati, importazione web, filtri locali e limiti della lista email non descrivevano più l'applicazione attuale. Gli script Alembic in `alembic/versions/` restano la fonte eseguibile per ogni modifica dello schema.

Per aggiornare il server seguire la procedura manuale in [DEPLOY](DEPLOY.md): SSH, su root, git pull, build Docker, backup e Alembic prima del riavvio. Gli script di deploy automatico e i relativi test sono stati rimossi. I tentativi precedenti non hanno modificato container o database.
