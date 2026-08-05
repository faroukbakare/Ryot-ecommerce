from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from main.models import Product, Cart, CartItem

class CartRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpassword', email='test@example.com')
        
        # Create a dummy product
        image = SimpleUploadedFile("product.jpg", b"file_content", content_type="image/jpeg")
        self.product = Product.objects.create(
            name='Test Product',
            description='Test Description',
            price=10.00,
            image=image,
            sizes=['M', 'L']
        )

    def test_unauthenticated_cart_access(self):
        """Verify unauthenticated users can access the cart page (200 OK)."""
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 200)

    def test_buy_now_view_requires_login(self):
        """Verify accessing buy_now directly redirects to login page."""
        response = self.client.post(f'/buy-now/{self.product.id}/', {'quantity': 1, 'size': 'M'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/sign-in/', response.url)

    def test_checkout_requires_login(self):
        """Verify checkout view requires authentication."""
        response = self.client.get('/checkout/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/sign-in/', response.url)

    def test_login_redirect_to_next(self):
        """Verify that signing in redirects to the 'next' parameter if provided."""
        checkout_url = '/checkout/'
        response = self.client.get('/sign-in/', {'next': checkout_url})
        self.assertEqual(response.status_code, 200)
        self.assertIn('next', response.context)
        self.assertEqual(response.context['next'], checkout_url)

        response = self.client.post('/sign-in/', {
            'username': 'testuser',
            'password': 'testpassword',
            'next': checkout_url
        })
        self.assertRedirects(response, checkout_url)

    def test_cart_merging_on_login(self):
        """Verify that items in a guest session cart are merged into the user cart upon login."""
        response = self.client.post('/ajax/add-to-cart/', {
            'product_id': self.product.id,
            'quantity': 2,
            'size': 'M'
        })
        self.assertEqual(response.status_code, 200)
        
        guest_carts = Cart.objects.filter(user=None)
        self.assertEqual(guest_carts.count(), 1)
        guest_cart = guest_carts.first()
        self.assertEqual(guest_cart.items.filter(product=self.product, size='M').first().quantity, 2)

        response = self.client.post('/sign-in/', {
            'username': 'testuser',
            'password': 'testpassword'
        })
        self.assertEqual(response.status_code, 302)

        self.assertFalse(Cart.objects.filter(user=None).exists())
        
        user_cart = Cart.objects.get(user=self.user)
        user_item = user_cart.items.filter(product=self.product, size='M').first()
        self.assertIsNotNone(user_item)
        self.assertEqual(user_item.quantity, 2)

    def test_invalid_login_shows_error_message(self):
        """Verify that logging in with invalid credentials returns an error message on the sign-in page."""
        response = self.client.post('/sign-in/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Invalid username or password.")
        self.assertContains(response, "Invalid username or password.")
