from django.db.models import Count

from .models import Cart, CartItem


def get_cart(request, create=True):
    if request.user.is_authenticated:
        if create:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            clean_duplicate_cart_items(cart)
            return cart
        else:
            cart = Cart.objects.filter(user=request.user).first()
            if cart:
                clean_duplicate_cart_items(cart)
            return cart
    else:
        session_key = request.session.session_key
        if not session_key:
            if not create:
                return None
            request.session.create()
            session_key = request.session.session_key

        if create:
            cart, _ = Cart.objects.get_or_create(
                user=None,
                session_key=session_key
            )
            clean_duplicate_cart_items(cart)
            return cart
        else:
            cart = Cart.objects.filter(user=None, session_key=session_key).first()
            if cart:
                clean_duplicate_cart_items(cart)
            return cart


def clean_duplicate_cart_items(cart):
    duplicates = (
        CartItem.objects.filter(cart=cart)
        .values('product', 'size')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    for duplicate in duplicates:
        items = CartItem.objects.filter(
            cart=cart,
            product_id=duplicate['product'],
            size=duplicate['size']
        ).order_by('id')
        master = items.first()
        if master:
            for extra in items[1:]:
                master.quantity += extra.quantity
                extra.delete()
            master.save()
