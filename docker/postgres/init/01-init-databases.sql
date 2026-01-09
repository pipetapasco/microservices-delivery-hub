SELECT 'CREATE DATABASE pedidos_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'pedidos_db')\gexec


SELECT 'CREATE DATABASE mototaxis_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mototaxis_db')\gexec

\echo '==========================================='
\echo 'PostgreSQL initialization completed!'
\echo 'Databases created: pedidos_db, mototaxis_db'
\echo '==========================================='