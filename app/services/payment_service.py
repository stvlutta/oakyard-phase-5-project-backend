import stripe
from flask import current_app
from decimal import Decimal
import os

# Initialize Stripe
def init_stripe():
    """Initialize Stripe with secret key"""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

def create_payment_intent(amount, currency='usd', metadata=None):
    """Create a Stripe payment intent"""
    init_stripe()
    
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,  # Amount in cents
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return intent
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Payment intent creation failed: {e}")

def confirm_payment(payment_intent_id):
    """Confirm a payment intent"""
    init_stripe()
    
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Payment confirmation failed: {e}")

def create_refund(payment_intent_id, amount=None, reason=None):
    """Create a refund for a payment"""
    init_stripe()
    
    try:
        refund_data = {
            'payment_intent': payment_intent_id,
        }
        
        if amount:
            refund_data['amount'] = amount
        
        if reason:
            refund_data['reason'] = reason
        
        refund = stripe.Refund.create(**refund_data)
        return refund
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Refund creation failed: {e}")

def get_payment_intent(payment_intent_id):
    """Get payment intent details"""
    init_stripe()
    
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Payment intent retrieval failed: {e}")

def handle_webhook(payload, signature):
    """Handle Stripe webhook events"""
    init_stripe()
    
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
    except ValueError as e:
        current_app.logger.error(f"Invalid payload: {e}")
        raise Exception("Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Invalid signature: {e}")
        raise Exception("Invalid signature")
    
    # Handle different event types
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_success(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_payment_failure(payment_intent)
    elif event['type'] == 'charge.dispute.created':
        dispute = event['data']['object']
        handle_chargeback(dispute)
    
    return event

def handle_payment_success(payment_intent):
    """Handle successful payment"""
    from app import db
    from app.models.booking import Booking
    from app.services.email_service import send_booking_confirmation_email, send_new_booking_notification
    
    # Get booking from metadata
    booking_id = payment_intent.get('metadata', {}).get('booking_id')
    if not booking_id:
        return
    
    booking = Booking.query.get(booking_id)
    if not booking:
        return
    
    # Update booking status
    booking.status = 'confirmed'
    booking.payment_status = 'paid'
    db.session.commit()
    
    # Send emails
    try:
        send_booking_confirmation_email(booking)
        send_new_booking_notification(booking)
    except Exception as e:
        current_app.logger.error(f"Failed to send confirmation emails: {e}")

def handle_payment_failure(payment_intent):
    """Handle failed payment"""
    from app import db
    from app.models.booking import Booking
    
    # Get booking from metadata
    booking_id = payment_intent.get('metadata', {}).get('booking_id')
    if not booking_id:
        return
    
    booking = Booking.query.get(booking_id)
    if not booking:
        return
    
    # Update booking status
    booking.status = 'cancelled'
    booking.payment_status = 'failed'
    db.session.commit()

def handle_chargeback(dispute):
    """Handle chargeback/dispute"""
    from app import db
    from app.models.booking import Booking
    
    # Get charge details
    charge_id = dispute.get('charge')
    if not charge_id:
        return
    
    try:
        charge = stripe.Charge.retrieve(charge_id)
        payment_intent_id = charge.get('payment_intent')
        
        if payment_intent_id:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            booking_id = payment_intent.get('metadata', {}).get('booking_id')
            
            if booking_id:
                booking = Booking.query.get(booking_id)
                if booking:
                    booking.payment_status = 'disputed'
                    db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to handle chargeback: {e}")

def calculate_platform_fee(amount, fee_percentage=0.03):
    """Calculate platform fee"""
    return Decimal(amount) * Decimal(fee_percentage)

def calculate_total_with_fees(amount, fee_percentage=0.03):
    """Calculate total amount including platform fees"""
    platform_fee = calculate_platform_fee(amount, fee_percentage)
    return amount + platform_fee

def create_connect_account(email, country='US'):
    """Create a Stripe Connect account for space owners"""
    init_stripe()
    
    try:
        account = stripe.Account.create(
            type='express',
            country=country,
            email=email,
        )
        return account
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Connect account creation failed: {e}")

def create_account_link(account_id, refresh_url, return_url):
    """Create account link for Connect onboarding"""
    init_stripe()
    
    try:
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type='account_onboarding',
        )
        return account_link
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Account link creation failed: {e}")

def transfer_to_connected_account(amount, destination_account, metadata=None):
    """Transfer money to connected account"""
    init_stripe()
    
    try:
        transfer = stripe.Transfer.create(
            amount=amount,
            currency='usd',
            destination=destination_account,
            metadata=metadata or {},
        )
        return transfer
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Transfer failed: {e}")

def get_balance():
    """Get Stripe account balance"""
    init_stripe()
    
    try:
        balance = stripe.Balance.retrieve()
        return balance
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Balance retrieval failed: {e}")

def create_customer(email, name=None):
    """Create a Stripe customer"""
    init_stripe()
    
    try:
        customer_data = {'email': email}
        if name:
            customer_data['name'] = name
        
        customer = stripe.Customer.create(**customer_data)
        return customer
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Customer creation failed: {e}")

def get_payment_methods(customer_id):
    """Get customer's payment methods"""
    init_stripe()
    
    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card',
        )
        return payment_methods
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Payment methods retrieval failed: {e}")

def create_setup_intent(customer_id):
    """Create setup intent for saving payment method"""
    init_stripe()
    
    try:
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=['card'],
        )
        return setup_intent
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Setup intent creation failed: {e}")

def process_subscription_payment(customer_id, price_id, metadata=None):
    """Process subscription payment"""
    init_stripe()
    
    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            metadata=metadata or {},
        )
        return subscription
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Subscription creation failed: {e}")

def cancel_subscription(subscription_id):
    """Cancel a subscription"""
    init_stripe()
    
    try:
        subscription = stripe.Subscription.delete(subscription_id)
        return subscription
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Subscription cancellation failed: {e}")

def get_transaction_history(limit=100):
    """Get transaction history"""
    init_stripe()
    
    try:
        charges = stripe.Charge.list(limit=limit)
        return charges
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        raise Exception(f"Transaction history retrieval failed: {e}")

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')  # Replace with your test key or set in env

# You can set your domain here or pass it from the frontend
DOMAIN = os.getenv('FRONTEND_DOMAIN', 'http://localhost:8080')

def create_checkout_session(amount, currency='kes', metadata=None):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'product_data': {
                        'name': 'Space Booking',
                    },
                    'unit_amount': int(amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{DOMAIN}/payment-success',
            cancel_url=f'{DOMAIN}/payment-cancel',
            metadata=metadata or {},
        )
        return session.url
    except Exception as e:
        print(f'Stripe error: {e}')
        return None