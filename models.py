import logging
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# User model
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with bookings
    bookings = db.relationship('Booking', backref='user', lazy=True)
    
    # Password reset tokens
    reset_tokens = db.relationship('PasswordResetToken', backref='user', lazy=True)
    
    # Flask-Login integration
    @property
    def is_authenticated(self):
        return True
        
    @property
    def is_active(self):
        return True
        
    @property
    def is_anonymous(self):
        return False
        
    def get_id(self):
        return str(self.id)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @classmethod
    def get_by_email(cls, email):
        return cls.query.filter_by(email=email).first()
    
    @classmethod
    def get_by_username(cls, username):
        return cls.query.filter_by(username=username).first()

# Password Reset Token model
class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expiry = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    @classmethod
    def generate_token(cls, user):
        # Delete any existing tokens for this user
        cls.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        # Generate a new token
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=40))
        expiry = datetime.utcnow() + timedelta(hours=1)  # Token valid for 1 hour
        
        # Create and save the token
        reset_token = cls(token=token, user_id=user.id, expiry=expiry)
        db.session.add(reset_token)
        db.session.commit()
        
        return token
    
    @classmethod
    def verify_token(cls, token):
        token_obj = cls.query.filter_by(token=token, used=False).first()
        
        if not token_obj:
            return None
        
        if token_obj.expiry < datetime.utcnow():
            return None
        
        return token_obj.user

# OTP model for booking verification
class OTP(db.Model):
    __tablename__ = 'otps'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)  # 'booking', 'login', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    @classmethod
    def generate_otp(cls, email, purpose):
        # Delete any existing OTPs for this email and purpose
        cls.query.filter_by(email=email, purpose=purpose).delete()
        db.session.commit()
        
        # Generate a new OTP
        otp_code = ''.join(random.choices(string.digits, k=6))  # 6-digit OTP
        expiry = datetime.utcnow() + timedelta(minutes=10)  # OTP valid for 10 minutes
        
        # Create and save the OTP
        otp = cls(code=otp_code, email=email, purpose=purpose, expiry=expiry)
        db.session.add(otp)
        db.session.commit()
        
        return otp_code
    
    @classmethod
    def verify_otp(cls, email, code, purpose):
        otp = cls.query.filter_by(email=email, code=code, purpose=purpose, used=False).first()
        
        if not otp:
            return False
        
        if otp.expiry < datetime.utcnow():
            return False
        
        # Mark OTP as used
        otp.used = True
        db.session.commit()
        
        return True

# Booking model
class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    booking_type = db.Column(db.String(20), nullable=False)  # 'hotel', 'flight', 'package'
    item_id = db.Column(db.Integer, nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)  # May be null for one-way flights
    adults = db.Column(db.Integer, default=1)
    children = db.Column(db.Integer, default=0)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'confirmed', 'cancelled'
    
    @classmethod
    def get_user_bookings(cls, user_id):
        return cls.query.filter_by(user_id=user_id).order_by(cls.booking_date.desc()).all()
    
    def get_item_details(self):
        if self.booking_type == 'hotel':
            return Hotel.query.get(self.item_id)
        elif self.booking_type == 'flight':
            return Flight.query.get(self.item_id)
        elif self.booking_type == 'package':
            return Package.query.get(self.item_id)
        return None

# Hotel model
class Hotel(db.Model):
    __tablename__ = 'hotels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    rating = db.Column(db.Numeric(3, 1))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    
    @classmethod
    def get_all_hotels(cls):
        try:
            return cls.query.order_by(cls.price.asc()).all()
        except Exception as e:
            logging.error(f"Error fetching hotels: {e}")
            return []
    
    @classmethod
    def get_hotel_by_id(cls, hotel_id):
        try:
            return cls.query.get(hotel_id)
        except Exception as e:
            logging.error(f"Error fetching hotel {hotel_id}: {e}")
            return None

# Flight model
class Flight(db.Model):
    __tablename__ = 'flights'
    
    id = db.Column(db.Integer, primary_key=True)
    airline = db.Column(db.String(255), nullable=False)
    departure_city = db.Column(db.String(255), nullable=False)
    arrival_city = db.Column(db.String(255), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)
    arrival_time = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.Text)
    
    @classmethod
    def get_all_flights(cls):
        try:
            return cls.query.order_by(cls.departure_time.asc()).all()
        except Exception as e:
            logging.error(f"Error fetching flights: {e}")
            return []
    
    @classmethod
    def get_flight_by_id(cls, flight_id):
        try:
            return cls.query.get(flight_id)
        except Exception as e:
            logging.error(f"Error fetching flight {flight_id}: {e}")
            return None

# Package model
class Package(db.Model):
    __tablename__ = 'packages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    destination = db.Column(db.String(255), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    included_services = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    
    @classmethod
    def get_all_packages(cls):
        try:
            return cls.query.order_by(cls.price.asc()).all()
        except Exception as e:
            logging.error(f"Error fetching packages: {e}")
            return []
    
    @classmethod
    def get_package_by_id(cls, package_id):
        try:
            return cls.query.get(package_id)
        except Exception as e:
            logging.error(f"Error fetching package {package_id}: {e}")
            return None

# ChatbotResponse model
class ChatbotResponse(db.Model):
    __tablename__ = 'chatbot_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(255), nullable=False)
    response = db.Column(db.Text, nullable=False)

    # Method to seed the database with default chatbot responses
    @classmethod
    def seed_default_responses(cls):
        # Check if responses already exist
        if cls.query.count() == 0:
            default_responses = [
                ('hello', 'Hello! Welcome to TravelWise. How can I help you plan your next trip?'),
                ('hi', 'Hi there! Looking to plan a vacation? I can help with hotels, flights, and travel packages.'),
                ('hotel', 'We have a wide range of hotels available. You can browse our hotel deals section for the best rates.'),
                ('flight', 'Check out our flight packages for great deals on airfare to popular destinations.'),
                ('package', 'Our travel packages include hotel stays, flights, and sometimes additional perks like meals or activities.'),
                ('help', 'I can help you find hotels, flights, or travel packages. What would you like assistance with?'),
                ('thanks', 'You\'re welcome! Let me know if you need any more help with your travel plans.'),
                ('thank you', 'You\'re welcome! Feel free to ask if you have more questions about our travel services.'),
                ('booking', 'To make a booking, browse our listings and click on the "Book Now" button for the option you prefer.'),
                ('cancel', 'To cancel a booking, please contact our customer service team through the contact form.'),
                ('price', 'Our prices vary depending on the destination, time of travel, and accommodations. Browse our listings for specific pricing.'),
                ('contact', 'You can reach our customer service team at support@TravelWise.com or through the contact form on our website.'),
                ('discount', 'We frequently offer seasonal discounts and special promotions. Check our featured deals for the latest offers.'),
                ('covid', 'We provide up-to-date information on travel restrictions and safety measures. Please check destination-specific guidelines before booking.'),
                ('payment', 'We accept all major credit cards, PayPal, and bank transfers for payment.')
            ]
            
            for keyword, response in default_responses:
                db.session.add(cls(keyword=keyword, response=response))
            
            db.session.commit()
            logging.info("Default chatbot responses seeded successfully")

# Chatbot class for handling interactions
class Chatbot:
    @staticmethod
    def get_response(message):
        try:
            message_lower = message.lower()
            
            # Get all responses from the database
            responses = ChatbotResponse.query.all()
            
            # Default response if no keyword matches
            default_response = "I'm sorry, I don't understand that. Can you try asking about hotels, flights, or travel packages?"
            
            # Check if any keyword is in the message
            for resp in responses:
                if resp.keyword.lower() in message_lower:
                    return resp.response
            
            return default_response
        except Exception as e:
            logging.error(f"Error fetching chatbot response: {e}")
            return "Sorry, I'm having trouble right now. Please try again later."

# Search class for handling search functionality
class Search:
    @staticmethod
    def search_all(query):
        results = {
            'hotels': [],
            'flights': [],
            'packages': []
        }
        
        try:
            search_term = f"%{query}%"
            
            # Search hotels
            results['hotels'] = Hotel.query.filter(
                db.or_(
                    Hotel.name.ilike(search_term),
                    Hotel.location.ilike(search_term),
                    Hotel.description.ilike(search_term)
                )
            ).all()
            
            # Search flights
            results['flights'] = Flight.query.filter(
                db.or_(
                    Flight.airline.ilike(search_term),
                    Flight.departure_city.ilike(search_term),
                    Flight.arrival_city.ilike(search_term),
                    Flight.description.ilike(search_term)
                )
            ).all()
            
            # Search packages
            results['packages'] = Package.query.filter(
                db.or_(
                    Package.name.ilike(search_term),
                    Package.destination.ilike(search_term),
                    Package.description.ilike(search_term)
                )
            ).all()
            
        except Exception as e:
            logging.error(f"Error performing search: {e}")
        
        return results
