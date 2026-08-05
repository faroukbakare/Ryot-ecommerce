from .utils import get_cart


def cart_data(request):
    cart = get_cart(request, create=False)
    if cart:
        return {
            'cart_count': cart.total_items(),
            'cart_total': cart.total_price(),
        }
    return {
        'cart_count': 0,
        'cart_total': 0,
    }
