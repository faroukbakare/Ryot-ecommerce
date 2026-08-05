from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------
    # PUBLIC
    # ------------------------------
    path('', views.index, name='index'),
    path('products/', views.products, name='products'),
    path('products/<int:product_id>/', views.product_detail, name='product-detail'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

    # ------------------------------
    # AUTH
    # ------------------------------
    path('sign-up/', views.sign_up, name='sign-up'),
    path('sign-in/', views.sign_in, name='sign-in'),
    path('sign-out/', views.sign_out, name='sign-out'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # ------------------------------
    # CART
    # ------------------------------
    path('cart/', views.view_cart, name='cart'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),

    # ✅ AJAX CART
    path('ajax/add-to-cart/', views.add_to_cart, name='ajax-add-to-cart'),
    path('ajax/remove-from-cart/', views.remove_from_cart, name='ajax-remove-from-cart'),
    path('ajax/update-quantity/', views.update_quantity, name='update-quantity'),

    # ------------------------------
    # CHECKOUT
    # ------------------------------
    path('checkout/', views.checkout, name='checkout'),

    # ------------------------------
    # PAYMENT
    # ------------------------------
    path('initialize-payment/', views.initialize_payment, name='initialize_payment'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-failed/', views.payment_failed, name='payment_failed'),
]