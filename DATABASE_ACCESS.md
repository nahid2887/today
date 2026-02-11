# Database Access Information

Your PostgreSQL database is now accessible remotely. Use the following credentials to connect from another computer:

## Connection Details

| Parameter | Value |
|-----------|-------|
| **Host** | `localhost` or your machine IP address |
| **Port** | `5433` |
| **Database** | `hotel_db` |
| **Username** | `hotel_user` |
| **Password** | `hotel_pass` |

## Connection String

```
postgresql://hotel_user:hotel_pass@localhost:5433/hotel_db
```

## How to Connect from Remote Computer

### Option 1: Using psql (PostgreSQL CLI)
```bash
psql -h <your_machine_ip> -p 5433 -U hotel_user -d hotel_db
# Password: hotel_pass
```

### Option 2: Using DBeaver or pgAdmin
1. Create a new database connection
2. Set the following:
   - Host: `<your_machine_ip>` (replace with your actual IP)
   - Port: `5433`
   - Database: `hotel_db`
   - Username: `hotel_user`
   - Password: `hotel_pass`

### Option 3: Using Python (psycopg2)
```python
import psycopg2

conn = psycopg2.connect(
    host="<your_machine_ip>",
    port="5433",
    database="hotel_db",
    user="hotel_user",
    password="hotel_pass"
)
cursor = conn.cursor()
# Use cursor to execute queries
```

### Option 4: Using Node.js (pg)
```javascript
const { Client } = require('pg');

const client = new Client({
  host: '<your_machine_ip>',
  port: 5433,
  database: 'hotel_db',
  user: 'hotel_user',
  password: 'hotel_pass',
});

await client.connect();
// Use client to execute queries
```

### Option 5: Using Django ORM from another app
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hotel_db',
        'USER': 'hotel_user',
        'PASSWORD': 'hotel_pass',
        'HOST': '<your_machine_ip>',
        'PORT': '5433',
    }
}
```

## Find Your Machine IP Address

### On Windows (Command Prompt):
```bash
ipconfig
# Look for "IPv4 Address" under your network adapter
```

### On Mac/Linux (Terminal):
```bash
ifconfig
# or
hostname -I
```

## Tables Available

The database contains the following main tables:
- `hotel_hotel` - Hotel information
- `accounts_user` - User accounts
- `hotel_specialoffer` - Special offers
- `notifications_hotelnotification` - Notifications

## Web API Endpoints

The web application is also available at:
```
http://localhost:8000
```

## Important Notes

⚠️ **Security Warning**: This setup exposes your database on your local network. For production:
1. Change the default password to something secure
2. Use environment variables instead of hardcoding credentials
3. Implement firewall rules to restrict access
4. Use SSL/TLS for database connections
5. Never expose your database to the public internet without proper security measures

## Update docker-compose.yml for Production

To change credentials, edit `docker-compose.yml`:
```yaml
db:
  environment:
    POSTGRES_DB: your_db_name
    POSTGRES_USER: your_username
    POSTGRES_PASSWORD: your_secure_password
```

Then restart: `docker-compose down && docker-compose up -d`
