# Oakyard Backend API

A comprehensive backend API for Oakyard, a collaborative workspace booking platform built with Flask, SQLAlchemy, and Socket.IO.

## 🚀 Features

- **User Authentication & Authorization**: JWT-based authentication with role-based access control
- **Space Management**: Create, update, delete, and search workspace listings
- **Booking System**: Real-time booking functionality with conflict prevention
- **Real-time Communication**: Socket.IO integration for live updates and chat
- **Payment Integration**: Stripe payment processing for booking transactions
- **Email Notifications**: Automated email notifications for booking confirmations
- **File Upload**: Image upload support with AWS S3 integration
- **Admin Panel**: Administrative interface for managing users, spaces, and bookings
- **Rate Limiting**: API rate limiting to prevent abuse
- **Comprehensive Testing**: Unit and integration tests for all major features

## 🛠 Technology Stack

- **Framework**: Flask 2.3.3
- **Database**: SQLAlchemy with PostgreSQL (production) / SQLite (development)
- **Authentication**: Flask-JWT-Extended
- **Real-time**: Flask-SocketIO
- **Payment**: Stripe API
- **Email**: Flask-Mail
- **File Storage**: AWS S3 (optional)
- **Task Queue**: Celery with Redis
- **Testing**: pytest
- **Deployment**: Gunicorn + Eventlet

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL (for production)
- Redis server
- AWS S3 account (optional, for file uploads)
- Stripe account (for payments)

## 🔧 Installation

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd oakyard-phase-5-project-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   python init_db.py
   ```

6. **Start the development server**
   ```bash
   python run.py
   ```

The API will be available at `http://localhost:5000`

### Production Deployment

#### Deploy to Render

1. **Connect your repository to Render**
   - Sign up at [Render.com](https://render.com)
   - Connect your GitHub repository

2. **Use the render.yaml configuration**
   - The `render.yaml` file is pre-configured for deployment
   - Render will automatically detect and use this configuration

3. **Set environment variables**
   - Configure the required environment variables in Render dashboard
   - See `.env.example` for all required variables

4. **Deploy**
   - Push to your main branch
   - Render will automatically build and deploy

## 🏗 Project Structure

```
oakyard-phase-5-project-backend/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration settings
│   ├── models/                  # Database models
│   │   ├── user.py              # User model
│   │   ├── space.py             # Space model
│   │   ├── booking.py           # Booking model
│   │   ├── room.py              # Room model
│   │   ├── message.py           # Message model
│   │   └── review.py            # Review model
│   ├── routes/                  # API endpoints
│   │   ├── auth.py              # Authentication routes
│   │   ├── spaces.py            # Space management routes
│   │   ├── bookings.py          # Booking routes
│   │   ├── users.py             # User management routes
│   │   ├── admin.py             # Admin routes
│   │   └── meetings.py          # Meeting/room routes
│   ├── services/                # Business logic services
│   │   ├── email_service.py     # Email notifications
│   │   ├── payment_service.py   # Stripe integration
│   │   ├── image_service.py     # Image handling
│   │   └── notification_service.py # Notifications
│   ├── utils/                   # Utility functions
│   │   ├── decorators.py        # Custom decorators
│   │   ├── helpers.py           # Helper functions
│   │   ├── validators.py        # Input validation
│   │   └── socket_events.py     # Socket.IO events
│   └── seed_data.py             # Database seeding
├── tests/                       # Test suite
├── instance/                    # Instance folder (SQLite DB)
├── requirements.txt             # Python dependencies
├── run.py                       # Application entry point
├── init_db.py                   # Database initialization
├── celery_app.py                # Celery configuration
├── Dockerfile                   # Docker configuration
├── docker-compose.yml           # Docker Compose configuration
├── render.yaml                  # Render deployment config
├── Procfile                     # Process configuration
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## 🔌 API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh JWT token
- `POST /auth/logout` - User logout
- `GET /auth/me` - Get current user info

### Spaces
- `GET /spaces` - List all spaces (with filters)
- `POST /spaces` - Create new space
- `GET /spaces/{id}` - Get space details
- `PUT /spaces/{id}` - Update space
- `DELETE /spaces/{id}` - Delete space
- `POST /spaces/{id}/images` - Upload space images

### Bookings
- `GET /bookings` - List user bookings
- `POST /bookings` - Create booking
- `GET /bookings/{id}` - Get booking details
- `PUT /bookings/{id}` - Update booking
- `DELETE /bookings/{id}` - Cancel booking
- `POST /bookings/{id}/payment` - Process payment

### Users
- `GET /users/profile` - Get user profile
- `PUT /users/profile` - Update user profile
- `POST /users/avatar` - Upload profile picture

### Admin
- `GET /admin/users` - List all users
- `GET /admin/spaces` - List all spaces
- `GET /admin/bookings` - List all bookings
- `PUT /admin/users/{id}` - Update user status
- `DELETE /admin/spaces/{id}` - Delete space

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Flask environment | `development` |
| `SECRET_KEY` | Flask secret key | Required |
| `JWT_SECRET_KEY` | JWT signing key | Required |
| `DATABASE_URL` | Database connection string | `sqlite:///oakyard.db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `MAIL_SERVER` | SMTP server | `smtp.gmail.com` |
| `MAIL_USERNAME` | Email username | Required for email |
| `MAIL_PASSWORD` | Email password | Required for email |
| `STRIPE_SECRET_KEY` | Stripe secret key | Required for payments |
| `AWS_ACCESS_KEY_ID` | AWS access key | Optional |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Optional |
| `AWS_S3_BUCKET` | S3 bucket name | Optional |

### Database Models

#### User
- Authentication and profile information
- Role-based permissions (user, admin, owner)
- Profile picture and contact details

#### Space
- Workspace listings with details
- Location, amenities, pricing
- Image galleries and availability

#### Booking
- Reservation information
- Date/time ranges and status
- Payment tracking and special requests

#### Room
- Individual rooms within spaces
- Capacity and equipment details
- Real-time availability status

## 🚀 Deployment

### Render Deployment

1. **Fork/clone this repository**
2. **Connect to Render**: Link your GitHub repository
3. **Environment Variables**: Configure all required environment variables in Render dashboard
4. **Database**: Render will automatically provision PostgreSQL and Redis
5. **Deploy**: Push to main branch to trigger deployment

### Docker Deployment

```bash
# Build the image
docker build -t oakyard-backend .

# Run with docker-compose
docker-compose up -d
```

### Manual Server Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FLASK_ENV=production
export DATABASE_URL=postgresql://user:pass@host/db
# ... other environment variables

# Initialize database
python init_db.py

# Start with Gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 run:app
```

## 🔒 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: bcrypt password hashing
- **Rate Limiting**: API endpoint rate limiting
- **CORS Configuration**: Configurable cross-origin resource sharing
- **Input Validation**: Comprehensive input validation and sanitization
- **SQL Injection Prevention**: SQLAlchemy ORM protections

## 📈 Monitoring & Logging

- **Application Logs**: Configurable logging levels
- **Error Tracking**: Built-in error handling and reporting
- **Performance Monitoring**: Request timing and database query monitoring
- **Health Checks**: Endpoint health check for deployment monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 API Documentation

For detailed API documentation with request/response examples, visit:
- Development: `http://localhost:5000/docs` (when implemented)
- Production: `https://your-domain.com/docs`

## 🐛 Known Issues

- Socket.IO connections may require additional CORS configuration for some frontend frameworks
- Large file uploads may timeout on slower connections
- Celery tasks require Redis to be running

## 🔮 Future Enhancements

- [ ] GraphQL API support
- [ ] Advanced search with Elasticsearch
- [ ] Mobile push notifications
- [ ] Calendar integration (Google Calendar, Outlook)
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Automated testing with CI/CD

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For support, email support@oakyard.com or create an issue in this repository.

---

**Oakyard Backend API** - Built with ❤️ for collaborative workspace management