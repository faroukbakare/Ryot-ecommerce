"""
RIOT Streetwear — Automated Marketing Emails
=============================================
Central module for all 8 automated email scenarios.
Each function builds an HTML email using Django templates and sends via EmailMultiAlternatives.
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from .models import EmailLog

logger = logging.getLogger(__name__)


def _get_site_url():
    """Return the base site URL from settings."""
    return getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')


def _send_email(user, email_type, subject, template_name, context, reference_id=None):
    """
    Internal helper: renders an HTML template, sends the email,
    and logs it in EmailLog to prevent duplicate sends.
    """
    if not user.email:
        logger.warning(f"Skipping {email_type} email for {user.username}: no email address.")
        return False

    # Add common context
    context.update({
        'user': user,
        'username': user.first_name or user.username,
        'site_url': _get_site_url(),
        'current_year': timezone.now().year,
    })

    try:
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Log the sent email
        EmailLog.objects.create(
            user=user,
            email_type=email_type,
            subject=subject,
            reference_id=reference_id,
        )

        logger.info(f"✅ Sent {email_type} email to {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send {email_type} email to {user.email}: {e}")
        return False


# ============================================================
# 1. WELCOME EMAIL
# ============================================================
def send_welcome_email(user):
    """
    Triggered: immediately after user registration.
    Content: brand intro, first-purchase discount code RIOT15.
    """
    return _send_email(
        user=user,
        email_type='welcome',
        subject='Welcome to RIOT 🔥 — Your 15% Off Awaits',
        template_name='emails/welcome.html',
        context={
            'discount_code': 'RIOT15',
            'discount_percent': 15,
        },
    )


# ============================================================
# 2. ABANDONED CART EMAIL
# ============================================================
def send_abandoned_cart_email(user, cart):
    """
    Triggered: by scheduled command when cart has items but no checkout for 1+ hour.
    Content: cart items with images, urgency messaging.
    """
    cart_items = cart.items.select_related('product').all()
    if not cart_items.exists():
        return False

    return _send_email(
        user=user,
        email_type='abandoned_cart',
        subject="You left some heat behind 🔥 — Your cart's waiting",
        template_name='emails/abandoned_cart.html',
        context={
            'cart_items': cart_items,
            'cart_total': cart.total_price(),
            'cart_url': f"{_get_site_url()}/cart/",
        },
        reference_id=cart.id,
    )


# ============================================================
# 3. ORDER CONFIRMATION EMAIL
# ============================================================
def send_order_confirmation_email(order):
    """
    Triggered: immediately after successful payment verification.
    Content: order summary, item list, total, reference.
    """
    order_items = order.items.select_related('product').all()

    return _send_email(
        user=order.user,
        email_type='order_confirmation',
        subject=f'Order Confirmed #{order.id} — RIOT Has Your Back 🖤',
        template_name='emails/order_confirmation.html',
        context={
            'order': order,
            'order_items': order_items,
            'dashboard_url': f"{_get_site_url()}/dashboard/",
        },
        reference_id=order.id,
    )


# ============================================================
# 4. POST-PURCHASE FOLLOW-UP EMAIL
# ============================================================
def send_post_purchase_email(order):
    """
    Triggered: by scheduled command 5 days after order was paid.
    Content: styling tips, review request, social sharing CTA.
    """
    order_items = order.items.select_related('product').all()

    return _send_email(
        user=order.user,
        email_type='post_purchase',
        subject='How\'s your RIOT fit? 🤘 Share your look',
        template_name='emails/post_purchase.html',
        context={
            'order': order,
            'order_items': order_items,
            'products_url': f"{_get_site_url()}/products/",
        },
        reference_id=order.id,
    )


# ============================================================
# 5. WIN-BACK (INACTIVE CUSTOMER) EMAIL
# ============================================================
def send_winback_email(user):
    """
    Triggered: by scheduled command when user has been inactive for 30+ days.
    Content: exclusive comeback discount, new arrivals teaser.
    """
    return _send_email(
        user=user,
        email_type='winback',
        subject='We miss you at RIOT 💀 — Here\'s 20% off to come back',
        template_name='emails/winback.html',
        context={
            'discount_code': 'RIOTCOMEBACK20',
            'discount_percent': 20,
            'products_url': f"{_get_site_url()}/products/",
        },
    )


# ============================================================
# 6. NEW DROP ALERT EMAIL
# ============================================================
def send_new_drop_alert(product, users=None):
    """
    Triggered: via signal when a Product with is_new=True is created,
    or manually via admin action.
    Sends to all users with an email address (or a specific list).
    """
    from django.contrib.auth.models import User

    if users is None:
        users = User.objects.exclude(email='').exclude(email__isnull=True)

    sent_count = 0
    for user in users:
        success = _send_email(
            user=user,
            email_type='new_drop',
            subject=f'🚨 NEW DROP: {product.name} Just Landed at RIOT',
            template_name='emails/new_drop.html',
            context={
                'product': product,
                'product_url': f"{_get_site_url()}/products/{product.id}/",
            },
            reference_id=product.id,
        )
        if success:
            sent_count += 1

    logger.info(f"New drop alert for '{product.name}' sent to {sent_count} users.")
    return sent_count


# ============================================================
# 7. ANNIVERSARY EMAIL
# ============================================================
def send_anniversary_email(user):
    """
    Triggered: by scheduled command on the anniversary of account creation.
    Content: loyalty reward, personalized message.
    """
    years = (timezone.now() - user.date_joined).days // 365

    return _send_email(
        user=user,
        email_type='anniversary',
        subject=f'🎂 Happy {years}-Year Anniversary with RIOT!',
        template_name='emails/anniversary.html',
        context={
            'years': years,
            'discount_code': f'RIOTOG{years}',
            'discount_percent': min(10 + (years * 5), 30),  # 15%, 20%, 25%, cap at 30%
            'products_url': f"{_get_site_url()}/products/",
        },
    )


# ============================================================
# 8. BACK-IN-STOCK EMAIL
# ============================================================
def send_back_in_stock_email(user, product):
    """
    Triggered: when a product is restocked (future wishlist/notify-me feature).
    Content: product details, urgency CTA.
    """
    return _send_email(
        user=user,
        email_type='back_in_stock',
        subject=f'🔄 Back in Stock: {product.name} — Don\'t Sleep on It',
        template_name='emails/back_in_stock.html',
        context={
            'product': product,
            'product_url': f"{_get_site_url()}/products/{product.id}/",
        },
        reference_id=product.id,
    )
