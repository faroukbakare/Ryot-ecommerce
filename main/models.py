from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    sizes = models.JSONField(default=list, blank=True)
    is_new = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['name']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'product'
            slug = base_slug
            counter = 1
            while Product.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product-detail', kwargs={'product_id': self.id})


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
        ]

    def total_price(self):
        return sum(item.total_price() for item in self.items.select_related('product').all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Cart {self.id}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    size = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        unique_together = ('cart', 'product', 'size')
        indexes = [
            models.Index(fields=['cart', 'product', 'size']),
        ]

    def total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f'{self.quantity} × {self.product.name}'


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_reference = models.CharField(max_length=200, unique=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['payment_reference']), models.Index(fields=['created_at'])]

    def __str__(self):
        return f"Order {self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    size = models.CharField(max_length=50, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return f'{self.quantity} × {self.product.name} for Order {self.order_id}'


class EmailLog(models.Model):
    """Tracks which automated emails have been sent to prevent duplicates."""
    EMAIL_TYPES = [
        ('welcome', 'Welcome'),
        ('abandoned_cart', 'Abandoned Cart'),
        ('order_confirmation', 'Order Confirmation'),
        ('post_purchase', 'Post-Purchase Follow-Up'),
        ('winback', 'Win-Back'),
        ('new_drop', 'New Drop Alert'),
        ('anniversary', 'Anniversary'),
        ('back_in_stock', 'Back in Stock'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='email_logs'
    )
    email_type = models.CharField(max_length=30, choices=EMAIL_TYPES)
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', 'email_type', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.email_type} → {self.user.username} ({self.sent_at:%Y-%m-%d %H:%M})"
