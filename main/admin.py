from django.contrib import admin
from .models import Product, Cart, CartItem, Order, OrderItem, EmailLog


# ------------------------------
# CART AND ITEMS
# ------------------------------
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'created_at')
    inlines = [CartItemInline]
    search_fields = ('user__username', 'session_key')


# ------------------------------
# ORDER AND ITEMS
# ------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'payment_reference', 'is_paid', 'created_at')
    list_filter = ('is_paid', 'created_at')
    inlines = [OrderItemInline]
    search_fields = ('user__username', 'payment_reference')


# ------------------------------
# PRODUCT (with New Drop action)
# ------------------------------
def send_new_drop_alert_action(modeladmin, request, queryset):
    """Admin action: manually send new drop alert for selected products."""
    from .emails import send_new_drop_alert
    from django.contrib import messages as django_messages

    total_sent = 0
    for product in queryset:
        count = send_new_drop_alert(product)
        total_sent += count

    django_messages.success(
        request,
        f"New drop alert sent to {total_sent} users for {queryset.count()} product(s)."
    )

send_new_drop_alert_action.short_description = "📧 Send New Drop Alert email to all users"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_new')
    search_fields = ('name', 'description')
    actions = [send_new_drop_alert_action]


# ------------------------------
# EMAIL LOG
# ------------------------------
@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('email_type', 'user', 'subject', 'sent_at')
    list_filter = ('email_type', 'sent_at')
    search_fields = ('user__username', 'user__email', 'subject')
    readonly_fields = ('user', 'email_type', 'subject', 'sent_at', 'reference_id')
    date_hierarchy = 'sent_at'

    def has_add_permission(self, request):
        return False  # Logs are auto-generated, not manually created
