# YouSpeak Backend

Production-ready FastAPI backend built for global scale with authentication, PostgreSQL, Redis caching, rate limiting, and comprehensive API documentation.

## Features

- 🚀 **FastAPI** - Modern, high-performance web framework
- 🔐 **JWT Authentication** - Secure token-based authentication with refresh tokens
- 🗄️ **PostgreSQL** - Robust relational database with async support
- 🔴 **Redis** - Caching and rate limiting
- 📊 **SQLAlchemy 2.0** - Modern ORM with async support
- 🔄 **Alembic** - Database migration management
- 🛡️ **Security** - CORS, rate limiting, security headers
- 📝 **Auto-generated Documentation** - OpenAPI/Swagger UI
- 🐳 **Docker** - Containerized for easy deployment
- ✅ **Testing** - Pytest with async support
- 📊 **Structured Logging** - JSON logging for production

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis (optional, for rate limiting)

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd youspeak_backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run database migrations**
```bash
alembic upgrade head
```

6. **Start the development server**
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

### Docker Development

1. **Start all services**
```bash
docker-compose up -d
```

2. **Run migrations**
```bash
docker-compose exec api alembic upgrade head
```

3. **View logs**
```bash
docker-compose logs -f api
```

4. **Stop services**
```bash
docker-compose down
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Users
- `GET /api/v1/users` - List users (paginated)
- `GET /api/v1/users/{id}` - Get user by ID
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user (superuser only)
- `POST /api/v1/users/change-password` - Change password

## Database Migrations

### Create a new migration
```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
```

## Testing

### Unit tests (no database required)
```bash
pytest tests/unit_test.py -v
```

### Integration & E2E tests (require DATABASE_URL, SECRET_KEY)
Ensure PostgreSQL is running and `.env` has `DATABASE_URL` and `SECRET_KEY`. Run migrations first:
```bash
alembic upgrade head
pytest tests/integration/ tests/e2e/ -v
```

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app tests/ --no-cov-on-fail
```

### Test structure
- `tests/unit_test.py` - Unit tests (config, no external deps)
- `tests/integration/` - Per-endpoint integration tests (auth, schools, admin, students, teachers, classes, references, users)
- `tests/e2e/` - Full flow E2E tests (school onboarding, teacher+student flow)

### Run CI checks locally (before pushing)
Lint, Docker Compose, and tests—same as GitHub Actions, without pushing:

```bash
./scripts/run-ci-local.sh
```

See [docs/LOCAL_CI.md](docs/LOCAL_CI.md) for options and for running the full workflow with [act](https://github.com/nektos/act).

## Project Structure

```
youspeak_backend/
├── app/
│   ├── api/                    # API routes
│   │   ├── v1/
│   │   │   ├── endpoints/     # API endpoints
│   │   │   └── router.py      # Router configuration
│   │   └── deps.py            # Dependencies
│   ├── core/                   # Core functionality
│   │   ├── security.py        # Auth & security
│   │   ├── logging.py         # Logging config
│   │   └── middleware.py      # Custom middleware
│   ├── models/                 # Database models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   ├── config.py               # Configuration
│   ├── database.py             # Database setup
│   └── main.py                 # App entry point
├── alembic/                    # Database migrations
├── tests/                      # Test suite
├── .env                        # Environment variables
├── .env.example                # Environment template
├── docker-compose.yml          # Docker compose config
├── Dockerfile                  # Docker image
├── requirements.txt            # Production dependencies
└── requirements-dev.txt        # Development dependencies
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret key (min 32 characters)
- `REDIS_URL` - Redis connection string
- `ALLOWED_ORIGINS` - CORS allowed origins
- `RESEND_API_KEY` - Resend API key for teacher invite emails (optional; when unset, emails are logged only)

## Deployment

### Production Checklist

1. ✅ Update `SECRET_KEY` with a strong random value
2. ✅ Set `ENVIRONMENT=production`
3. ✅ Set `DEBUG=False`
4. ✅ Configure proper `ALLOWED_ORIGINS`
5. ✅ Use managed PostgreSQL and Redis
6. ✅ Set up SSL/TLS certificates
7. ✅ Configure monitoring and logging
8. ✅ Set up backup strategy

### Build Docker Image
```bash
docker build -t youspeak-backend:latest .
```

### Run Production Container
```bash
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name youspeak-api \
  youspeak-backend:latest
```

## Code Quality

### Format code
```bash
black app/ tests/
```

### Lint code
```bash
ruff check app/ tests/
```

### Type checking
```bash
mypy app/
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
