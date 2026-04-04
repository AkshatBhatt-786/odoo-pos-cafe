from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, Http404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .models import (
    Floor, Table, Product, Category, PaymentMethod,
    POSSession, Order, OrderLine, KitchenTicket, ProductVariant
)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _get_or_open_session(user):
    """Return open session for user, or create a new one."""
    session = POSSession.objects.filter(user=user, status="open").first()
    if not session:
        session = POSSession.objects.create(user=user)
    return session


def _session_required(view_func):
    """Decorator: ensures user has an open POS session."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        _get_or_open_session(request.user)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─────────────────────────────────────────────
#  SESSION MANAGEMENT
# ─────────────────────────────────────────────

@login_required
def open_session_view(request):
    """Opens a new POS session and redirects to floor view."""
    session = _get_or_open_session(request.user)
    messages.success(request, f"Session #{session.pk} is now open.")
    return redirect("pos:floor")


@login_required
@require_POST
def close_session_view(request):
    """Closes the current POS session."""
    session = POSSession.objects.filter(user=request.user, status="open").first()
    if session:
        session.close()
        messages.info(request, f"Session #{session.pk} closed. Total: ₹{session.closing_sale_amount}")
    return redirect("pos:backend")


# ─────────────────────────────────────────────
#  FLOOR VIEW  (B2)
# ─────────────────────────────────────────────

@login_required
def floor_view(request):
    session = _get_or_open_session(request.user)
    floors = Floor.objects.filter(is_active=True).prefetch_related("tables")
    context = {
        "session": session,
        "floors": floors,
    }
    return render(request, "pos/floor.html", context)


# ─────────────────────────────────────────────
#  ORDER SCREEN  (B3)
# ─────────────────────────────────────────────

@login_required
def order_view(request, table_id):
    table = get_object_or_404(Table, pk=table_id, is_active=True)
    session = _get_or_open_session(request.user)

    # Get or create the open order for this table in this session
    order = Order.objects.filter(
        session=session, table=table, status__in=["open", "sent"]
    ).first()
    if not order:
        order = Order.objects.create(session=session, table=table)

    categories = Category.objects.prefetch_related("products").filter(
        products__is_available=True
    ).distinct()

    context = {
        "session": session,
        "table": table,
        "order": order,
        "categories": categories,
        "lines": order.lines.select_related("product", "variant").all(),
    }
    return render(request, "pos/order.html", context)


@login_required
@require_POST
def add_item_view(request, order_id):
    """AJAX: add product to order line (or increment qty)."""
    order = get_object_or_404(Order, pk=order_id, session__user=request.user, status__in=["open", "sent"])
    product_id = request.POST.get("product_id")
    variant_id = request.POST.get("variant_id") or None
    product = get_object_or_404(Product, pk=product_id, is_available=True)
    variant = None
    unit_price = product.price
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
        unit_price += variant.extra_price

    line, created = OrderLine.objects.get_or_create(
        order=order, product=product, variant=variant,
        defaults={"unit_price": unit_price, "tax_rate": product.tax_rate},
    )
    if not created:
        line.quantity += 1
        line.save()

    order.recalculate()
    return JsonResponse({
        "ok": True,
        "line_id": line.pk,
        "qty": line.quantity,
        "subtotal": str(order.subtotal),
        "grand_total": str(order.grand_total),
    })


@login_required
@require_POST
def update_item_view(request, line_id):
    """AJAX: set quantity (0 = remove)."""
    line = get_object_or_404(OrderLine, pk=line_id, order__session__user=request.user)
    qty = int(request.POST.get("qty", 0))
    if qty <= 0:
        line.delete()
    else:
        line.quantity = qty
        line.save()
    line.order.recalculate()
    return JsonResponse({"ok": True, "grand_total": str(line.order.grand_total)})


@login_required
@require_POST
def send_to_kitchen_view(request, order_id):
    """Mark order as sent and create/update KitchenTicket."""
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    if not order.lines.exists():
        messages.error(request, "Cannot send empty order to kitchen.")
        return redirect("pos:order", table_id=order.table_id)

    order.status = Order.SENT
    order.save()

    KitchenTicket.objects.get_or_create(order=order)
    messages.success(request, f"Order #{order.pk} sent to kitchen.")
    return redirect("pos:order", table_id=order.table_id)


# ─────────────────────────────────────────────
#  PAYMENT SCREEN  (B4 / B5)
# ─────────────────────────────────────────────

@login_required
def payment_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    payment_methods = PaymentMethod.objects.filter(is_enabled=True)
    upi_method = payment_methods.filter(type="upi").first()

    context = {
        "order": order,
        "payment_methods": payment_methods,
        "upi_method": upi_method,
        "lines": order.lines.select_related("product").all(),
    }
    return render(request, "pos/payment.html", context)


@login_required
@require_POST
def process_payment_view(request, order_id):
    """Validate payment and mark order as paid."""
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    method = request.POST.get("method")

    allowed = [pm.type for pm in PaymentMethod.objects.filter(is_enabled=True)]
    if method not in allowed:
        messages.error(request, "Invalid payment method.")
        return redirect("pos:payment", order_id=order_id)

    order.payment_method = method
    order.status = Order.PAID
    order.save()
    messages.success(request, f"Payment confirmed via {order.get_payment_method_display()}.")
    return redirect("pos:payment_confirm", order_id=order.pk)


@login_required
def payment_confirm_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, session__user=request.user, status="paid")
    return render(request, "pos/payment_confirm.html", {"order": order})


# ─────────────────────────────────────────────
#  KITCHEN DISPLAY  (B7)
# ─────────────────────────────────────────────

def kitchen_view(request):
    """Kitchen display — no login required (kiosk-style)."""
    tickets = KitchenTicket.objects.exclude(stage="completed").select_related(
        "order", "order__table"
    ).prefetch_related("order__lines__product")
    completed = KitchenTicket.objects.filter(stage="completed").select_related(
        "order", "order__table"
    ).order_by("-updated_at")[:10]
    return render(request, "pos/kitchen.html", {"tickets": tickets, "completed": completed})


@require_POST
def advance_ticket_view(request, ticket_id):
    """AJAX: advance kitchen ticket stage."""
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    ticket.advance()
    return JsonResponse({"ok": True, "stage": ticket.stage})


@require_POST
def mark_line_prepared_view(request, line_id):
    """AJAX: mark order line as prepared (strike-through)."""
    line = get_object_or_404(OrderLine, pk=line_id)
    line.is_prepared = not line.is_prepared
    line.save()
    return JsonResponse({"ok": True, "prepared": line.is_prepared})


# ─────────────────────────────────────────────
#  CUSTOMER DISPLAY  (B6)
# ─────────────────────────────────────────────

def customer_display_view(request, order_id):
    """Customer-facing display — no auth required."""
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "pos/customer_display.html", {
        "order": order,
        "lines": order.lines.select_related("product").all(),
    })


# ─────────────────────────────────────────────
#  SELF-ORDERING  (A6 Optional)
# ─────────────────────────────────────────────

def self_order_view(request, token):
    """Mobile/self-ordering by token."""
    order = get_object_or_404(Order, self_order_token=token)
    categories = Category.objects.prefetch_related("products").filter(
        products__is_available=True
    ).distinct()

    if request.method == "POST":
        product_id = request.POST.get("product_id")
        product = get_object_or_404(Product, pk=product_id, is_available=True)
        line, created = OrderLine.objects.get_or_create(
            order=order, product=product,
            defaults={"unit_price": product.price, "tax_rate": product.tax_rate},
        )
        if not created:
            line.quantity += 1
            line.save()
        order.recalculate()
        # Auto-send to kitchen
        if order.status == Order.OPEN:
            order.status = Order.SENT
            order.save()
            KitchenTicket.objects.get_or_create(order=order)

    return render(request, "pos/self_order.html", {
        "order": order,
        "categories": categories,
        "lines": order.lines.select_related("product").all(),
    })


# ─────────────────────────────────────────────
#  POS BACKEND CONFIG  (A2–A5)
# ─────────────────────────────────────────────

@login_required
def backend_view(request):
    """Backend config dashboard."""
    session = POSSession.objects.filter(user=request.user, status="open").first()
    last_closed = POSSession.objects.filter(user=request.user, status="closed").order_by("-closed_at").first()

    context = {
        "session": session,
        "last_closed": last_closed,
        "product_count": Product.objects.count(),
        "category_count": Category.objects.count(),
        "floor_count": Floor.objects.filter(is_active=True).count(),
        "table_count": Table.objects.filter(is_active=True).count(),
        "payment_methods": PaymentMethod.objects.all(),
        "floors": Floor.objects.prefetch_related("tables").filter(is_active=True),
        "products": Product.objects.select_related("category").all(),
        "categories": Category.objects.all(),
    }
    return render(request, "pos/backend.html", context)


@login_required
@require_POST
def toggle_payment_method_view(request, pm_id):
    pm = get_object_or_404(PaymentMethod, pk=pm_id)
    pm.is_enabled = not pm.is_enabled
    pm.save()
    return JsonResponse({"ok": True, "enabled": pm.is_enabled})


# ─────────────────────────────────────────────
#  REPORTS  (A8)
# ─────────────────────────────────────────────

@login_required
def reports_view(request):
    from django.db.models import Sum, Count, Q
    from datetime import date, timedelta

    # --- Filters ---
    period = request.GET.get("period", "today")
    session_id = request.GET.get("session_id", "")
    responsible_id = request.GET.get("responsible_id", "")
    product_id = request.GET.get("product_id", "")

    orders = Order.objects.filter(status="paid")

    today = date.today()
    if period == "today":
        orders = orders.filter(updated_at__date=today)
    elif period == "week":
        orders = orders.filter(updated_at__date__gte=today - timedelta(days=7))
    elif period == "custom":
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        if date_from:
            orders = orders.filter(updated_at__date__gte=date_from)
        if date_to:
            orders = orders.filter(updated_at__date__lte=date_to)

    if session_id:
        orders = orders.filter(session_id=session_id)
    if responsible_id:
        orders = orders.filter(session__user_id=responsible_id)
    if product_id:
        orders = orders.filter(lines__product_id=product_id)

    agg = orders.aggregate(
        total_revenue=Sum("grand_total"),
        total_orders=Count("id", distinct=True),
    )

    from django.contrib.auth.models import User as DjangoUser
    context = {
        "orders": orders.select_related("table", "session__user").order_by("-updated_at")[:50],
        "total_revenue": agg["total_revenue"] or 0,
        "total_orders": agg["total_orders"] or 0,
        "period": period,
        "sessions": POSSession.objects.order_by("-opened_at")[:20],
        "users": DjangoUser.objects.filter(pos_sessions__isnull=False).distinct(),
        "products": Product.objects.all(),
        "selected_session": session_id,
        "selected_responsible": responsible_id,
        "selected_product": product_id,
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }
    return render(request, "pos/reports.html", context)