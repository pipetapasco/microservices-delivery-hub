db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || 'db_empresas');

db.createUser({
    user: process.env.MONGO_APP_USER || 'app_user',
    pwd: process.env.MONGO_APP_PASSWORD || 'app_password',
    roles: [
        {
            role: 'readWrite',
            db: process.env.MONGO_INITDB_DATABASE || 'db_empresas'
        }
    ]
});

db.createCollection('menus', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['empresa_id', 'nombre', 'created_at'],
            properties: {
                empresa_id: {
                    bsonType: 'objectId',
                    description: 'ID de la empresa - requerido'
                },
                nombre: {
                    bsonType: 'string',
                    description: 'Nombre del menú - requerido'
                },
                items: {
                    bsonType: 'array',
                    description: 'Items del menú'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'Fecha de creación - requerido'
                },
                updated_at: {
                    bsonType: 'date',
                    description: 'Fecha de última actualización'
                }
            }
        }
    }
});

db.createCollection('usuarios_empresas', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['email', 'password_hash', 'created_at'],
            properties: {
                email: {
                    bsonType: 'string',
                    description: 'Email del usuario - requerido'
                },
                password_hash: {
                    bsonType: 'string',
                    description: 'Hash de la contraseña - requerido'
                },
                empresa_id: {
                    bsonType: 'objectId',
                    description: 'ID de la empresa asociada'
                },
                is_active: {
                    bsonType: 'bool',
                    description: 'Estado de la cuenta'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'Fecha de creación - requerido'
                }
            }
        }
    }
});

db.menus.createIndex({ 'empresa_id': 1 });
db.menus.createIndex({ 'nombre': 1 });
db.usuarios_empresas.createIndex({ 'email': 1 }, { unique: true });
db.usuarios_empresas.createIndex({ 'empresa_id': 1 });

print('===========================================');
print('MongoDB initialization completed!');
print('Database: ' + (process.env.MONGO_INITDB_DATABASE || 'db_empresas'));
print('Collections: menus, usuarios_empresas');
print('===========================================');
