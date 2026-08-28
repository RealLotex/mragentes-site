# Contrato de entrega social

La skill sólo produce un draft cerrado y su recurso. Un workflow confiable valida de nuevo el schema y el hash, toma exclusión por `dedupe_key` y usa el entorno `meta-testing` mientras la aplicación permanezca en testing.

Facebook e Instagram se registran por separado. Cada ID remoto confirmado se persiste de inmediato; un fallo en una plataforma no borra el éxito de la otra. Un re-run consulta el ledger antes de cualquier efecto y omite plataformas ya completas.

No incluyas tokens, captions completas ni endpoints sensibles en reportes. Las credenciales viven fuera del repositorio y nunca se solicitan desde la skill.
