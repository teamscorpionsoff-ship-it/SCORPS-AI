# Privacy

The local demo stores account email/name, password hashes, tasks, explicitly saved memories, chat messages, and extracted document text in a local SQLite database. The demo does not send this information to an LLM or search service. Local originals also reside under UPLOAD_DIR. In production, extracted text resides in PostgreSQL and originals reside in a private Supabase bucket. The document deletion endpoint removes the original and its database record. Document delete UI and account deletion are not yet provided. Never upload sensitive records to an untrusted deployment.
