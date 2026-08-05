import logging
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def handle_user_login(sender, user, request, **kwargs):
    """Merge guest cart into user cart on login."""
    from .views import merge_session_cart
    merge_session_cart(request, user)


@receiver(post_save, sender='main.Product')
def handle_new_product(sender, instance, created, **kwargs):
    """
    When a new Product with is_new=True is created via admin,
    send a new drop alert to all subscribed users.
    """
    if created and instance.is_new:
        from .emails import send_new_drop_alert
        try:
            count = send_new_drop_alert(instance)
            logger.info(f"New drop alert sent to {count} users for '{instance.name}'")
        except Exception as e:
            logger.error(f"Failed to send new drop alerts: {e}")
