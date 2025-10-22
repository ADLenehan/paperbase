# Paperbase Deployment Guide

This guide covers deploying Paperbase from development to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Database Setup](#database-setup)
6. [Service Dependencies](#service-dependencies)
7. [Monitoring & Logging](#monitoring--logging)
8. [Backup & Recovery](#backup--recovery)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **Git** for version control
- **8GB+ RAM** for Elasticsearch
- **20GB+ disk space** for document storage

### API Keys

You'll need API keys from:

1. **Reducto** - Get from [https://reducto.ai](https://reducto.ai)
   - Sign up for account
   - Navigate to API settings
   - Generate new API key

2. **Anthropic Claude** - Get from [https://console.anthropic.com](https://console.anthropic.com)
   - Create account
   - Go to API keys section
   - Generate new key

---

## Development Deployment

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd paperbase
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Configure environment**:
   ```bash
   # Edit .env with your API keys
   nano .env

   # Required:
   REDUCTO_API_KEY=your_reducto_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   ```

4. **Start services**:
   ```bash
   docker-compose up --build
   ```

5. **Verify deployment**:
   ```bash
   # Backend health check
   curl http://localhost:8000/health

   # Frontend (open in browser)
   open http://localhost:3000
   ```

### Development Workflow

#### Backend Development

Run backend locally without Docker:

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Development

Run frontend locally:

```bash
cd frontend

# Install dependencies
npm install

# Run development server with hot reload
npm run dev
```

#### Running Tests

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Frontend tests (when implemented)
cd frontend
npm test
```

---

## Production Deployment

### Architecture Overview

```
┌─────────────┐
│  Nginx      │ ← Reverse proxy + SSL termination
│  (Port 80)  │
└──────┬──────┘
       │
       ├─→ Frontend (Port 3000)
       └─→ Backend (Port 8000)
            │
            ├─→ Reducto API
            ├─→ Claude API
            ├─→ Elasticsearch (Port 9200)
            └─→ PostgreSQL (Production DB)
```

### Option 1: Docker Compose (Single Server)

**Suitable for**: <1000 documents/day, <5 concurrent users

1. **Update docker-compose.prod.yml**:

   ```yaml
   version: '3.8'

   services:
     backend:
       build:
         context: ./backend
         dockerfile: Dockerfile.prod
       environment:
         - DATABASE_URL=postgresql://user:pass@postgres:5432/paperbase
         - ELASTICSEARCH_URL=http://elasticsearch:9200
       depends_on:
         - postgres
         - elasticsearch
       restart: always

     frontend:
       build:
         context: ./frontend
         dockerfile: Dockerfile.prod
       restart: always

     nginx:
       image: nginx:alpine
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
         - ./certs:/etc/nginx/certs
       depends_on:
         - backend
         - frontend
       restart: always

     postgres:
       image: postgres:15-alpine
       environment:
         POSTGRES_DB: paperbase
         POSTGRES_USER: paperbase
         POSTGRES_PASSWORD: ${DB_PASSWORD}
       volumes:
         - postgres_data:/var/lib/postgresql/data
       restart: always

     elasticsearch:
       image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
       environment:
         - discovery.type=single-node
         - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
       volumes:
         - es_data:/usr/share/elasticsearch/data
       restart: always

   volumes:
     postgres_data:
     es_data:
   ```

2. **Deploy**:

   ```bash
   # Build and start
   docker-compose -f docker-compose.prod.yml up -d --build

   # Check logs
   docker-compose -f docker-compose.prod.yml logs -f

   # Check status
   docker-compose -f docker-compose.prod.yml ps
   ```

### Option 2: Kubernetes (Multi-Server)

**Suitable for**: >1000 documents/day, high availability needed

See `k8s/` directory for Kubernetes manifests (coming soon).

---

## Environment Configuration

### Production Environment Variables

Create `.env.production`:

```bash
# API Keys (REQUIRED)
REDUCTO_API_KEY=your_production_key
ANTHROPIC_API_KEY=your_production_key

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://user:password@host:5432/paperbase

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200
# For managed Elasticsearch (e.g., AWS):
# ELASTICSEARCH_URL=https://your-es-domain.us-east-1.es.amazonaws.com

# Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=false
LOG_LEVEL=WARNING

# File Upload
MAX_UPLOAD_SIZE_MB=100
UPLOAD_DIR=/app/uploads

# Processing
REDUCTO_TIMEOUT=600
CONFIDENCE_THRESHOLD_LOW=0.6
CONFIDENCE_THRESHOLD_HIGH=0.8

# Security (add in production)
SECRET_KEY=your-secret-key-here-minimum-32-chars
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Monitoring (optional)
SENTRY_DSN=your-sentry-dsn
```

### Security Considerations

1. **Never commit `.env` files** - Use `.env.example` templates only
2. **Use secret management** - Consider AWS Secrets Manager, HashiCorp Vault
3. **Rotate API keys** - Especially after team changes
4. **Enable HTTPS** - Required for production
5. **Add authentication** - Before multi-user deployment

---

## Database Setup

### Migration from SQLite to PostgreSQL

For production, migrate from SQLite to PostgreSQL:

1. **Install PostgreSQL client**:
   ```bash
   pip install psycopg2-binary
   ```

2. **Update DATABASE_URL**:
   ```bash
   DATABASE_URL=postgresql://user:password@host:5432/paperbase
   ```

3. **Run migrations** (when using Alembic):
   ```bash
   alembic upgrade head
   ```

4. **Migrate data** (if needed):
   ```bash
   # Export from SQLite
   sqlite3 paperbase.db .dump > dump.sql

   # Import to PostgreSQL (manual conversion may be needed)
   psql -U user -d paperbase -f dump.sql
   ```

### Database Backups

**Automated daily backups**:

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# PostgreSQL backup
pg_dump -U paperbase paperbase > $BACKUP_DIR/paperbase_$DATE.sql

# Compress
gzip $BACKUP_DIR/paperbase_$DATE.sql

# Delete backups older than 30 days
find $BACKUP_DIR -name "paperbase_*.sql.gz" -mtime +30 -delete
```

Add to crontab:
```bash
0 2 * * * /path/to/backup.sh
```

---

## Service Dependencies

### Elasticsearch

**System Requirements**:
- Minimum: 4GB RAM, 2 CPU cores
- Recommended: 8GB RAM, 4 CPU cores

**Configuration**:

```yaml
# elasticsearch.yml
cluster.name: paperbase
node.name: paperbase-node-1

# Memory
bootstrap.memory_lock: true

# Network
network.host: 0.0.0.0
http.port: 9200

# Security (production)
xpack.security.enabled: true
xpack.security.transport.ssl.enabled: true
```

**Index Templates**:

Paperbase automatically creates indices, but you can optimize:

```bash
# Create index with custom settings
curl -X PUT "localhost:9200/paperbase_documents" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "filename": { "type": "keyword" },
      "content": { "type": "text" },
      "extractions": { "type": "object" },
      "uploaded_at": { "type": "date" }
    }
  }
}
'
```

### Reducto API

**Rate Limits**:
- Free tier: 100 documents/month
- Pro tier: 1000 documents/month
- Enterprise: Custom limits

**Monitoring**:
```bash
# Check Reducto status
curl https://status.reducto.ai/api/v2/status.json
```

### Claude API

**Rate Limits** (as of Jan 2025):
- Tier 1: 50 requests/day
- Tier 2: 1000 requests/day
- Enterprise: Custom limits

**Cost Optimization**:
- Claude is only called during onboarding and weekly improvements
- Expected usage: <10 requests/week for typical workload
- Monitor via Anthropic Console

---

## Monitoring & Logging

### Application Logs

**Centralized logging** (production):

```yaml
# docker-compose.prod.yml logging config
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Log aggregation** with Loki:

```bash
# Add Loki and Grafana to docker-compose
docker-compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

### Health Checks

**Endpoint**: `GET /health`

**Monitoring script**:

```bash
#!/bin/bash
# health_check.sh

BACKEND_URL="http://localhost:8000"

response=$(curl -s -o /dev/null -w "%{http_code}" $BACKEND_URL/health)

if [ $response -eq 200 ]; then
    echo "✓ Backend healthy"
    exit 0
else
    echo "✗ Backend unhealthy (HTTP $response)"
    exit 1
fi
```

### Metrics

**Key metrics to track**:

1. **Processing metrics**:
   - Documents processed/hour
   - Average processing time
   - Error rate

2. **API metrics**:
   - Request rate
   - Response time (p50, p95, p99)
   - Error rate by endpoint

3. **Resource metrics**:
   - CPU usage
   - Memory usage
   - Disk usage
   - Elasticsearch heap usage

**Prometheus integration** (optional):

```python
# Add to backend/app/main.py
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(...)
Instrumentator().instrument(app).expose(app)
```

---

## Backup & Recovery

### Backup Checklist

- [ ] **Database**: Daily automated backups
- [ ] **Uploaded documents**: Sync to S3/cloud storage
- [ ] **Elasticsearch indices**: Weekly snapshots
- [ ] **Configuration**: Version controlled in Git
- [ ] **Environment variables**: Securely stored separately

### Document Storage Backup

```bash
# Sync uploads to S3
aws s3 sync /app/uploads s3://paperbase-backups/uploads/$(date +%Y%m%d)

# Or use rsync
rsync -av /app/uploads/ backup-server:/backups/uploads/
```

### Disaster Recovery

**RTO (Recovery Time Objective)**: <4 hours
**RPO (Recovery Point Objective)**: <24 hours

**Recovery steps**:

1. **Restore database**:
   ```bash
   psql -U paperbase paperbase < latest_backup.sql
   ```

2. **Restore documents**:
   ```bash
   aws s3 sync s3://paperbase-backups/uploads/latest /app/uploads
   ```

3. **Restore Elasticsearch**:
   ```bash
   curl -X POST "localhost:9200/_snapshot/my_backup/snapshot_1/_restore"
   ```

4. **Verify**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/documents?limit=5
   ```

---

## Troubleshooting

### Elasticsearch Issues

**Symptom**: Elasticsearch won't start

```bash
# Check logs
docker-compose logs elasticsearch

# Common fixes:
# 1. Increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144

# 2. Ensure enough disk space (20GB+)
df -h

# 3. Reset if corrupted
docker-compose down -v
docker-compose up elasticsearch
```

**Symptom**: Out of memory errors

```bash
# Increase heap size in docker-compose.yml
environment:
  - "ES_JAVA_OPTS=-Xms4g -Xmx4g"  # Increase from 2g to 4g
```

### Backend Issues

**Symptom**: 502 Bad Gateway

```bash
# Check backend is running
docker-compose ps backend

# Check backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

**Symptom**: Reducto/Claude API errors

```bash
# Verify API keys
grep API_KEY .env

# Test Reducto connectivity
curl -H "Authorization: Bearer $REDUCTO_API_KEY" https://api.reducto.ai/v1/status

# Check rate limits in respective dashboards
```

### Database Issues

**Symptom**: Database connection errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U paperbase -d paperbase -c "SELECT 1;"

# Check connection string
echo $DATABASE_URL
```

**Symptom**: Slow queries

```bash
# Enable query logging
ALTER DATABASE paperbase SET log_min_duration_statement = 1000;

# Analyze slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

### Performance Issues

**Symptom**: Slow document processing

1. Check Reducto API latency
2. Verify network connectivity
3. Increase REDUCTO_TIMEOUT if needed
4. Monitor CPU/memory usage

**Symptom**: Slow search

1. Check Elasticsearch health: `curl localhost:9200/_cluster/health`
2. Optimize indices: `curl -X POST localhost:9200/paperbase_documents/_forcemerge`
3. Add more Elasticsearch nodes if needed

---

## Production Checklist

Before going live:

- [ ] All API keys configured and tested
- [ ] Database backups configured
- [ ] HTTPS/SSL certificates installed
- [ ] Monitoring and alerting set up
- [ ] Error tracking (Sentry) configured
- [ ] Log retention policy defined
- [ ] Security audit completed
- [ ] Load testing performed
- [ ] Disaster recovery plan documented
- [ ] Team trained on operations

---

## Scaling Considerations

### Horizontal Scaling

When you need to scale beyond single server:

1. **Load balancer** in front of multiple backend instances
2. **Shared storage** for uploads (S3, NFS)
3. **PostgreSQL** with read replicas
4. **Elasticsearch cluster** with multiple nodes
5. **Redis** for session caching

### Vertical Scaling

Recommended server specs by workload:

| Workload | CPU | RAM | Disk | Cost/month* |
|----------|-----|-----|------|-------------|
| Light (<100 docs/day) | 2 cores | 8GB | 50GB | ~$40 |
| Medium (<1000 docs/day) | 4 cores | 16GB | 200GB | ~$120 |
| Heavy (>1000 docs/day) | 8+ cores | 32GB+ | 500GB+ | ~$300+ |

*Approximate AWS/GCP pricing

---

## Support

For deployment issues:

1. Check logs: `docker-compose logs`
2. Review troubleshooting section
3. Search existing issues on GitHub
4. Create new issue with deployment details

---

**Last Updated**: January 2025
**Maintained by**: Paperbase Team
