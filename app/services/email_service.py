from flask import current_app
from flask_mail import Message
from app import mail
from celery import Celery
import os

def send_email(to, subject, template, **kwargs):
    """Send email using Flask-Mail"""
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            html=template,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False

def send_verification_email(email, name, token):
    """Send email verification email"""
    verification_url = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:3000')}/verify-email?token={token}"
    
    template = f"""
    <html>
        <body>
            <h2>Welcome to Oakyard!</h2>
            <p>Hi {name},</p>
            <p>Thank you for signing up with Oakyard. To complete your registration, please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
            <p>If you didn't create an account with us, please ignore this email.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=email,
        subject="Verify your Oakyard account",
        template=template
    )

def send_password_reset_email(email, name, token):
    """Send password reset email"""
    reset_url = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={token}"
    
    template = f"""
    <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Hi {name},</p>
            <p>You requested to reset your password. Click the link below to create a new password:</p>
            <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this password reset, please ignore this email.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=email,
        subject="Reset your Oakyard password",
        template=template
    )

def send_booking_confirmation_email(booking):
    """Send booking confirmation email"""
    user = booking.user
    space = booking.space
    
    template = f"""
    <html>
        <body>
            <h2>Booking Confirmation</h2>
            <p>Hi {user.name},</p>
            <p>Your booking has been confirmed! Here are the details:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Booking Details</h3>
                <p><strong>Space:</strong> {space.title}</p>
                <p><strong>Address:</strong> {space.address}</p>
                <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}</p>
                <p><strong>Total Amount:</strong> ${booking.total_amount}</p>
                <p><strong>Booking ID:</strong> {booking.id}</p>
            </div>
            
            <p>If you have any questions or need to make changes, please contact us.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=user.email,
        subject="Booking Confirmed - Oakyard",
        template=template
    )

def send_booking_cancellation_email(booking):
    """Send booking cancellation email"""
    user = booking.user
    space = booking.space
    
    template = f"""
    <html>
        <body>
            <h2>Booking Cancelled</h2>
            <p>Hi {user.name},</p>
            <p>Your booking has been cancelled. Here are the details:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Cancelled Booking Details</h3>
                <p><strong>Space:</strong> {space.title}</p>
                <p><strong>Address:</strong> {space.address}</p>
                <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}</p>
                <p><strong>Total Amount:</strong> ${booking.total_amount}</p>
                <p><strong>Booking ID:</strong> {booking.id}</p>
                {"<p><strong>Reason:</strong> " + booking.cancellation_reason + "</p>" if booking.cancellation_reason else ""}
            </div>
            
            <p>If you paid for this booking, a refund will be processed within 5-7 business days.</p>
            <p>If you have any questions, please contact us.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=user.email,
        subject="Booking Cancelled - Oakyard",
        template=template
    )

def send_space_approval_email(space):
    """Send space approval email to owner"""
    owner = space.owner
    
    template = f"""
    <html>
        <body>
            <h2>Space Approved!</h2>
            <p>Hi {owner.name},</p>
            <p>Great news! Your space has been approved and is now live on Oakyard.</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Space Details</h3>
                <p><strong>Title:</strong> {space.title}</p>
                <p><strong>Category:</strong> {space.category}</p>
                <p><strong>Hourly Rate:</strong> ${space.hourly_rate}</p>
                <p><strong>Address:</strong> {space.address}</p>
            </div>
            
            <p>Your space is now visible to users and can receive bookings.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=owner.email,
        subject="Space Approved - Oakyard",
        template=template
    )

def send_space_rejection_email(space, reason=None):
    """Send space rejection email to owner"""
    owner = space.owner
    
    template = f"""
    <html>
        <body>
            <h2>Space Submission Update</h2>
            <p>Hi {owner.name},</p>
            <p>We've reviewed your space submission and unfortunately it doesn't meet our current requirements.</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Space Details</h3>
                <p><strong>Title:</strong> {space.title}</p>
                <p><strong>Category:</strong> {space.category}</p>
                {"<p><strong>Reason:</strong> " + reason + "</p>" if reason else ""}
            </div>
            
            <p>Please review your submission and feel free to resubmit with the necessary changes.</p>
            <p>If you have any questions, please contact us.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=owner.email,
        subject="Space Submission Update - Oakyard",
        template=template
    )

def send_new_booking_notification(booking):
    """Send new booking notification to space owner"""
    owner = booking.space.owner
    user = booking.user
    space = booking.space
    
    template = f"""
    <html>
        <body>
            <h2>New Booking Received!</h2>
            <p>Hi {owner.name},</p>
            <p>You have received a new booking for your space:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Booking Details</h3>
                <p><strong>Space:</strong> {space.title}</p>
                <p><strong>Customer:</strong> {user.name} ({user.email})</p>
                <p><strong>Date & Time:</strong> {booking.start_time.strftime('%B %d, %Y at %I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}</p>
                <p><strong>Total Amount:</strong> ${booking.total_amount}</p>
                <p><strong>Booking ID:</strong> {booking.id}</p>
                {"<p><strong>Special Requests:</strong> " + booking.special_requests + "</p>" if booking.special_requests else ""}
            </div>
            
            <p>You can view more details in your dashboard.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=owner.email,
        subject="New Booking - Oakyard",
        template=template
    )

def send_review_notification(review):
    """Send review notification to space owner"""
    owner = review.space.owner
    user = review.user
    space = review.space
    
    stars = "★" * review.rating + "☆" * (5 - review.rating)
    
    template = f"""
    <html>
        <body>
            <h2>New Review Received!</h2>
            <p>Hi {owner.name},</p>
            <p>You have received a new review for your space:</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Review Details</h3>
                <p><strong>Space:</strong> {space.title}</p>
                <p><strong>Reviewer:</strong> {user.name}</p>
                <p><strong>Rating:</strong> {stars} ({review.rating}/5)</p>
                <p><strong>Comment:</strong> {review.comment}</p>
            </div>
            
            <p>You can view more details in your dashboard.</p>
            <p>Best regards,<br>The Oakyard Team</p>
        </body>
    </html>
    """
    
    return send_email(
        to=owner.email,
        subject="New Review - Oakyard",
        template=template
    )

# Celery task for sending emails asynchronously
def send_async_email(to, subject, template):
    """Send email asynchronously using Celery"""
    from app import create_app
    
    app = create_app()
    with app.app_context():
        return send_email(to, subject, template)