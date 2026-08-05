"""
RIOT Streetwear — Scheduled Marketing Emails
=============================================
Management command to process time-based email scenarios.

Run via:  python manage.py send_scheduled_emails
Schedule: Every hour via Windows Task Scheduler or cron

Handles:
  - Abandoned Cart  (cart idle > 1 hour, no recent order)
  - Post-Purchase   (paid order from 5 days ago)
  - Win-Back        (no login for 30+ days)
  - Anniversary     (account creation anniversary today)
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q

from main.models import Cart, Order, EmailLog
from main.emails import (
    send_abandoned_cart_email,
    send_post_purchase_email,
    send_winback_email,
    send_anniversary_email,
)


class Command(BaseCommand):
    help = 'Process and send scheduled marketing emails (abandoned cart, post-purchase, win-back, anniversary)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['abandoned_cart', 'post_purchase', 'winback', 'anniversary', 'all'],
            default='all',
            help='Run a specific scenario or all (default: all)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        scenario = options['scenario']
        dry_run = options['dry_run']
        now = timezone.now()

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No emails will be sent\n'))

        results = {}

        if scenario in ('abandoned_cart', 'all'):
            results['abandoned_cart'] = self._process_abandoned_carts(now, dry_run)

        if scenario in ('post_purchase', 'all'):
            results['post_purchase'] = self._process_post_purchase(now, dry_run)

        if scenario in ('winback', 'all'):
            results['winback'] = self._process_winback(now, dry_run)

        if scenario in ('anniversary', 'all'):
            results['anniversary'] = self._process_anniversaries(now, dry_run)

        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('[SUMMARY]'))
        for key, count in results.items():
            self.stdout.write(f'  {key}: {count} email(s) {"would be " if dry_run else ""}sent')
        self.stdout.write('=' * 50)

    def _process_abandoned_carts(self, now, dry_run):
        """
        Find authenticated users with cart items older than 1 hour
        who haven't placed an order in the last 24 hours
        and haven't received an abandoned cart email in the last 24 hours.
        """
        self.stdout.write(self.style.HTTP_INFO('\n[CART] Processing Abandoned Carts...'))

        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        # Carts belonging to logged-in users, last modified > 1 hour ago
        carts = Cart.objects.filter(
            user__isnull=False,
            items__isnull=False,
            created_at__lt=one_hour_ago,
        ).distinct().select_related('user')

        sent = 0
        for cart in carts:
            user = cart.user

            # Skip if no email
            if not user.email:
                continue

            # Skip if user placed an order in the last 24 hours
            if Order.objects.filter(user=user, is_paid=True, created_at__gte=one_day_ago).exists():
                continue

            # Skip if we already sent an abandoned cart email in the last 24 hours
            if EmailLog.objects.filter(
                user=user,
                email_type='abandoned_cart',
                sent_at__gte=one_day_ago,
            ).exists():
                continue

            if cart.items.count() == 0:
                continue

            if dry_run:
                self.stdout.write(f'  Would send to: {user.username} ({user.email}) — {cart.items.count()} items')
            else:
                success = send_abandoned_cart_email(user, cart)
                if success:
                    sent += 1
                    self.stdout.write(f'  ✅ Sent to: {user.username} ({user.email})')

        self.stdout.write(f'  → {sent} abandoned cart email(s) {"would be " if dry_run else ""}sent')
        return sent

    def _process_post_purchase(self, now, dry_run):
        """
        Find orders paid 5 days ago that haven't received a follow-up email.
        """
        self.stdout.write(self.style.HTTP_INFO('\n[ORDER] Processing Post-Purchase Follow-Ups...'))

        five_days_ago_start = (now - timedelta(days=5)).replace(hour=0, minute=0, second=0)
        five_days_ago_end = (now - timedelta(days=5)).replace(hour=23, minute=59, second=59)

        orders = Order.objects.filter(
            is_paid=True,
            created_at__range=(five_days_ago_start, five_days_ago_end),
        ).select_related('user')

        sent = 0
        for order in orders:
            user = order.user

            if not user.email:
                continue

            # Skip if already sent for this order
            if EmailLog.objects.filter(
                user=user,
                email_type='post_purchase',
                reference_id=order.id,
            ).exists():
                continue

            if dry_run:
                self.stdout.write(f'  Would send to: {user.username} — Order #{order.id}')
            else:
                success = send_post_purchase_email(order)
                if success:
                    sent += 1
                    self.stdout.write(f'  [OK] Sent to: {user.username} -- Order #{order.id}')

        self.stdout.write(f'  → {sent} post-purchase email(s) {"would be " if dry_run else ""}sent')
        return sent

    def _process_winback(self, now, dry_run):
        """
        Find users who haven't logged in or placed an order in 30+ days.
        Only send once per 30-day period.
        """
        self.stdout.write(self.style.HTTP_INFO('\n[WINBACK] Processing Win-Back Emails...'))

        thirty_days_ago = now - timedelta(days=30)

        # Users who haven't logged in for 30+ days
        inactive_users = User.objects.filter(
            last_login__lt=thirty_days_ago,
        ).exclude(
            email='',
        ).exclude(
            email__isnull=True,
        )

        sent = 0
        for user in inactive_users:
            # Skip if they placed a recent order
            if Order.objects.filter(user=user, is_paid=True, created_at__gte=thirty_days_ago).exists():
                continue

            # Skip if we already sent a winback email in the last 30 days
            if EmailLog.objects.filter(
                user=user,
                email_type='winback',
                sent_at__gte=thirty_days_ago,
            ).exists():
                continue

            if dry_run:
                self.stdout.write(f'  Would send to: {user.username} ({user.email}) — Last login: {user.last_login}')
            else:
                success = send_winback_email(user)
                if success:
                    sent += 1
                    self.stdout.write(f'  ✅ Sent to: {user.username} ({user.email})')

        self.stdout.write(f'  → {sent} win-back email(s) {"would be " if dry_run else ""}sent')
        return sent

    def _process_anniversaries(self, now, dry_run):
        """
        Find users whose account creation anniversary is today
        (same month and day, at least 1 year old).
        """
        self.stdout.write(self.style.HTTP_INFO('\n[ANNIVERSARY] Processing Anniversary Emails...'))

        today = now.date()

        # Find users who joined on this month/day in a previous year
        users = User.objects.filter(
            date_joined__month=today.month,
            date_joined__day=today.day,
        ).exclude(
            email='',
        ).exclude(
            email__isnull=True,
        )

        sent = 0
        for user in users:
            years = (today - user.date_joined.date()).days // 365
            if years < 1:
                continue  # Not yet a full year

            # Skip if already sent this year
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
            if EmailLog.objects.filter(
                user=user,
                email_type='anniversary',
                sent_at__gte=year_start,
            ).exists():
                continue

            if dry_run:
                self.stdout.write(f'  Would send to: {user.username} — {years} year(s)')
            else:
                success = send_anniversary_email(user)
                if success:
                    sent += 1
                    self.stdout.write(f'  [OK] Sent to: {user.username} -- {years} year(s)')

        self.stdout.write(f'  → {sent} anniversary email(s) {"would be " if dry_run else ""}sent')
        return sent
