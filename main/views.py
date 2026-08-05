from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Order, OrderItem, Product, Cart, CartItem
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .utils import get_cart
from .emails import send_welcome_email, send_order_confirmation_email


# ------------------------------
# PUBLIC PAGES
# ------------------------------
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import RegistrationForm, ContactForm, UserUpdateForm
from django.core.mail import send_mail

# ------------------------------
# PUBLIC PAGES
# ------------------------------
def index(request):
    products = Product.objects.all()
    return render(request, 'index.html', {'products': products})


def about(request):
    return render(request, 'about.html')


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            full_message = f"Message from {name} ({email}):\n\n{message}"
            try:
                send_mail(
                    subject=f"[Contact Form] {subject}",
                    message=full_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.DEFAULT_FROM_EMAIL],
                    fail_silently=False,
                )
                messages.success(request, "Your message has been sent successfully! We will get back to you soon.")
                return redirect('contact')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Contact email error: {e}")
                messages.error(request, "Unable to send message at this time. Please try again later.")
        else:
            messages.error(request, "Please fix the errors in the contact form.")
    else:
        form = ContactForm()

    return render(request, 'contact.html', {'form': form})


def products(request):
    products = Product.objects.all()
    return render(request, 'products.html', {'products': products})


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'product-detail.html', {'product': product})


# ------------------------------
# AUTHENTICATION
# ------------------------------
def sign_up(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            try:
                send_welcome_email(new_user)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Welcome email failed: {e}")
            messages.success(request, "Account created successfully. Please sign in.")
            return redirect('sign-in')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return render(request, 'sign-up.html', {'form': form})

    return render(request, 'sign-up.html', {'form': RegistrationForm()})


def merge_session_cart(request, user, guest_cart=None):
    if guest_cart is None:
        session_key = request.session.session_key
        if session_key:
            try:
                guest_cart = Cart.objects.get(session_key=session_key, user=None)
            except Cart.DoesNotExist:
                return None

    if not guest_cart:
        return None

    user_cart, _ = Cart.objects.get_or_create(user=user)
    for guest_item in guest_cart.items.all():
        user_item, created = CartItem.objects.get_or_create(
            cart=user_cart,
            product=guest_item.product,
            size=guest_item.size,
            defaults={'quantity': guest_item.quantity}
        )
        if not created:
            user_item.quantity += guest_item.quantity
            user_item.save()
    guest_cart.delete()
    return user_cart


def sign_in(request):
    next_url = request.GET.get('next') or request.POST.get('next') or 'index'
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')

        session_key = request.session.session_key
        user = authenticate(request, username=username, password=password)

        if user:
            guest_cart = None
            if session_key:
                try:
                    guest_cart = Cart.objects.get(session_key=session_key, user=None)
                except Cart.DoesNotExist:
                    pass

            login(request, user)
            merge_session_cart(request, user, guest_cart=guest_cart)

            if not url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                from django.urls import NoReverseMatch, reverse
                try:
                    next_url = reverse(next_url)
                except NoReverseMatch:
                    next_url = '/'
            return redirect(next_url)

        messages.error(request, "Invalid username or password.")
        return render(request, 'sign-in.html', {'next': next_url})

    return render(request, 'sign-in.html', {'next': next_url})


def sign_out(request):
    logout(request)
    return redirect('index')


@login_required(login_url='sign-in')
def dashboard(request):
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email
        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('dashboard')
        
    orders = Order.objects.filter(user=user).order_by('-created_at').prefetch_related('items__product')
    
    return render(request, 'dashboard.html', {
        'orders': orders,
        'user': user,
    })


# ------------------------------
# CART SYSTEM (FIXED)
# ------------------------------
def view_cart(request):
    cart = get_cart(request)

    return render(request, 'cart.html', {
        'cart_items': cart.items.all(),
        'cart_total': cart.total_price(),
        'cart_count': cart.total_items(),
    })


@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1)) # Get custom quantity selected by user
    size = request.POST.get('size')
    
    # Handle empty/null values sent from JavaScript
    if size in ['null', 'undefined', '']:
        size = None
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    # ✅ Retrieve or create the item with the specific size
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size
    )
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items(),
        'message': 'Added'
    })


@login_required(login_url='sign-in')
def buy_now(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    # Get size and quantity from GET or POST query parameters
    size = request.GET.get('size') or request.POST.get('size')
    quantity = int(request.GET.get('quantity') or request.POST.get('quantity') or 1)
    if size in ['null', 'undefined', '']:
        size = None
    # ✅ Retrieve or create with size
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size
    )
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    # ✅ Redirect straight to checkout
    return redirect('checkout')
    
    

def update_quantity(request):

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request'
        })

    item_id = request.POST.get('item_id')
    action = request.POST.get('action')

    cart = get_cart(request)

    try:
        item = CartItem.objects.get(
            id=item_id,
            cart=cart
        )

    except CartItem.DoesNotExist:

        return JsonResponse({
            'success': False,
            'message': 'Cart item not found'
        })

    # INCREASE
    if action == 'increase':

        item.quantity += 1
        item.save()

    # DECREASE
    elif action == 'decrease':

        item.quantity -= 1

        # REMOVE IF ZERO
        if item.quantity <= 0:

            item.delete()

            return JsonResponse({

                'success': True,

                'quantity': 0,

                'item_total': 0,

                'cart_total': cart.total_price(),

                'cart_count': cart.total_items(),

            })

        item.save()

    return JsonResponse({

        'success': True,

        'quantity': item.quantity,

        'item_total': item.total_price(),

        'cart_total': cart.total_price(),

        'cart_count': cart.total_items(),

    })


def remove_from_cart(request):

    if request.method != 'POST':

        return JsonResponse({
            'success': False,
            'message': 'Invalid request'
        })

    item_id = request.POST.get('item_id')

    cart = get_cart(request)

    try:

        item = CartItem.objects.get(
            id=item_id,
            cart=cart
        )

        item.delete()

    except CartItem.DoesNotExist:

        return JsonResponse({
            'success': False,
            'message': 'Item not found'
        })

    return JsonResponse({

        'success': True,

        'cart_total': cart.total_price(),

        'cart_count': cart.total_items(),

    })


# ------------------------------
# CHECKOUT (FIXED)
# ------------------------------
@login_required(login_url='sign-in')
def checkout(request):
    cart = get_cart(request)
    cart_items = cart.items.all()

    total = cart.total_price()

    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total
    })

import uuid
import requests

from django.conf import settings
from django.shortcuts import redirect

@login_required
def initialize_payment(request):

    cart = get_cart(request)

    if not cart.items.exists():
        return redirect('cart')

    # Validate that secret key is set
    if not getattr(settings, 'PAYSTACK_SECRET_KEY', None):
        messages.error(request, "Payment configuration error: Paystack secret key is missing. Please contact support.")
        return redirect('checkout')

    # Validate that user email is present
    if not request.user.email:
        messages.error(request, "An email address is required to proceed with payment. Please update your profile with a valid email.")
        return redirect('checkout')

    total = cart.total_price()

    reference = str(uuid.uuid4())

    order = Order.objects.create(
        user=request.user,
        total_amount=total,
        payment_reference=reference
    )

    for item in cart.items.all():

        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            size=item.size,
            price=item.product.price
        )

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    # Dynamically build callback URL using Django's reverse()
    from django.urls import reverse
    callback_url = request.build_absolute_uri(reverse('verify_payment'))

    data = {
        "email": request.user.email,
        "amount": int(total * 100),
        "reference": reference,
        "callback_url": callback_url
    }

    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers
        )
        response_data = response.json()
    except Exception as e:
        print(f"Error communicating with Paystack: {e}")
        messages.error(request, f"Error communicating with Paystack: {e}")
        return redirect('checkout')

    if response_data.get("status"):
        return redirect(
            response_data["data"]["authorization_url"]
        )

    # Log and display the error message from Paystack
    error_message = response_data.get("message", "Unknown error occurred during payment initialization.")
    print(f"Paystack Initialization Failed: {error_message}")
    messages.error(request, f"Payment initialization failed: {error_message}")

    return redirect('checkout')


@login_required
def verify_payment(request):

    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "No transaction reference provided.")
        return redirect('payment_failed')

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers
        )
        data = response.json()
    except Exception as e:
        print(f"Error communicating with Paystack: {e}")
        messages.error(request, "Unable to verify payment due to connection error. Please try again.")
        return redirect('payment_failed')

    if (
        data.get("status")
        and data.get("data", {}).get("status") == "success"
    ):
        try:
            order = Order.objects.get(
                payment_reference=reference
            )
        except Order.DoesNotExist:
            print(f"Order lookup failed for reference: {reference}")
            messages.error(request, "Order record not found for this transaction.")
            return redirect('payment_failed')

        if not order.is_paid:

            order.is_paid = True
            order.save()

            # Send order confirmation email (non-blocking)
            try:
                send_order_confirmation_email(order)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Order confirmation email failed: {e}")

            try:
                cart = Cart.objects.get(
                    user=request.user
                )
                cart.items.all().delete()
            except Cart.DoesNotExist:
                pass

        return redirect('payment_success')

    error_message = data.get("message", "Payment verification failed.")
    messages.error(request, f"Payment failed: {error_message}")
    return redirect('payment_failed')


@login_required
def payment_success(request):
    return render(request, 'payment_success.html')


@login_required
def payment_failed(request):
    return render(request, 'payment_failed.html')