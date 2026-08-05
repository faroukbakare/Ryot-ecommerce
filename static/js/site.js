function getCSRFToken() {
    const tokenInput = document.querySelector('#csrf-form [name=csrfmiddlewaretoken]');
    if (tokenInput && tokenInput.value) {
        return tokenInput.value;
    }
    const cookieName = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === cookieName) {
            return decodeURIComponent(value);
        }
    }
    return '';
}

function postForm(url, params) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(params).toString(),
    }).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        return response.json();
    });
}

function updateCartCount(count) {
    const cartBadge = document.getElementById('cart-count');
    if (!cartBadge) {
        return;
    }
    if (count > 0) {
        cartBadge.style.display = 'inline-block';
        cartBadge.textContent = count;
    } else {
        cartBadge.style.display = 'none';
    }
}

function updateCartTotals(data) {
    if (data.cart_total !== undefined) {
        const totalEl = document.getElementById('cart-total');
        if (totalEl) {
            totalEl.textContent = data.cart_total;
        }
    }
    if (data.cart_count !== undefined) {
        updateCartCount(data.cart_count);
        const cartHeader = document.getElementById('cart-count-header');
        if (cartHeader) {
            cartHeader.textContent = data.cart_count;
        }
    }
}

function showNotification(message, type = 'success') {
    const alertClass = type === 'error' ? 'alert-danger' : 'alert-success';
    const alertHolder = document.createElement('div');
    alertHolder.className = `alert ${alertClass} alert-dismissible fade show position-fixed top-0 end-0 m-3 shadow`;
    alertHolder.setAttribute('role', 'alert');
    alertHolder.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
    document.body.appendChild(alertHolder);
    setTimeout(() => {
        alertHolder.classList.remove('show');
        alertHolder.classList.add('fade');
        setTimeout(() => alertHolder.remove(), 300);
    }, 4000);
}

function cancelPreloader() {
    const preloader = document.querySelector('.preloader');
    if (preloader) {
        preloader.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    cancelPreloader();

    document.addEventListener('click', function (event) {
        const addButton = event.target.closest('.add-to-cart-btn');
        if (addButton) {
            event.preventDefault();
            const productId = addButton.dataset.productId;
            if (!productId) {
                return;
            }
            postForm('/ajax/add-to-cart/', {product_id: productId})
                .then(data => {
                    if (data.success) {
                        updateCartCount(data.cart_count);
                        showNotification('Product added to cart.');
                    }
                })
                .catch(() => showNotification('Unable to add item to cart.', 'error'));
            return;
        }

        const removeButton = event.target.closest('.remove-from-cart-btn');
        if (removeButton) {
            event.preventDefault();
            const itemId = removeButton.dataset.itemId;
            const row = removeButton.closest('.cart-item');
            postForm('/ajax/remove-from-cart/', {item_id: itemId})
                .then(data => {
                    if (data.success) {
                        if (row) {
                            row.remove();
                        }
                        updateCartTotals(data);
                        showNotification('Item removed from cart.');
                    }
                })
                .catch(() => showNotification('Unable to remove item from cart.', 'error'));
            return;
        }

        const qtyButton = event.target.closest('.increase, .decrease');
        if (qtyButton) {
            event.preventDefault();
            const itemId = qtyButton.dataset.itemId;
            const action = qtyButton.classList.contains('increase') ? 'increase' : 'decrease';
            const row = qtyButton.closest('.cart-item');
            postForm('/ajax/update-quantity/', {item_id: itemId, action: action})
                .then(data => {
                    if (data.success) {
                        if (row) {
                            const quantityEl = row.querySelector('.quantity');
                            const itemTotalEl = row.querySelector('.item-total');
                            if (data.quantity <= 0) {
                                row.remove();
                            } else {
                                if (quantityEl) quantityEl.textContent = data.quantity;
                                if (itemTotalEl) itemTotalEl.textContent = '₦' + data.item_total;
                            }
                        }
                        updateCartTotals(data);
                    }
                })
                .catch(() => showNotification('Unable to update quantity.', 'error'));
            return;
        }
    });
});
