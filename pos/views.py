from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, Http404
from urllib.parse import quote
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import (
    Floor, Table, Product, Category, PaymentMethod,
    POSSession, Order, OrderLine, KitchenTicket, ProductVariant
)


user = get_user_model()

# ============================================================================
# SECTION 1: HELPERS & DECORATORS
# ============================================================================
# These are internal utilities that keep our views DRY.
# The session management logic is centralized here so we don't repeat ourselves.
# ============================================================================

def _get_or_open_session(user):
    """
    Return an open POS session for the given user, or create a new one.
    
    This is called at the start of most views to ensure cashiers always have
    an active session. A user can only have ONE open session at a time due to
    the way we filter (status="open"). If they try to open another, we just
    return the existing one - no duplicates.
    """
    session = POSSession.objects.filter(user=user, status="open").first()
    if not session:
        session = POSSession.objects.create(user=user)
    return session


def _session_required(view_func):
    """
    Decorator that ensures a user has an open POS session before accessing a view.
    
    This is like @login_required but one level deeper - they need to be logged in
    AND have an active cashier session. Useful for views that assume a session exists.
    
    TODO: Consider merging this with @login_required and using Django's decorator chaining
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        _get_or_open_session(request.user)  # Auto-create if missing (silent behavior)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ============================================================================
# SECTION 2: SESSION MANAGEMENT (Cashier Shift Control)
# ============================================================================
# These views handle starting and ending a cashier's work shift.
# Opening a session is required before any POS operations can happen.
# Closing calculates total sales and locks the session for reporting.
# ============================================================================

@login_required
def open_session_view(request):
    """Opens a new POS session and redirects to floor view."""
    session = _get_or_open_session(request.user)
    messages.success(request, f"Session #{session.pk} is now open.")
    return redirect("pos:floor")


@login_required
@require_POST
def close_session_view(request):
    """
    Closes the current POS session.
    
    POST-only to prevent accidental closures via GET requests.
    The session.close() method calculates total sales from all paid orders
    and marks the session as closed. Once closed, no new orders can be added
    to this session.
    """
    session = POSSession.objects.filter(user=request.user, status="open").first()
    if session:
        session.close()
        messages.info(request, f"Session #{session.pk} closed. Total: ₹{session.closing_sale_amount}")
    return redirect("pos:backend")


# ============================================================================
# SECTION 3: FLOOR VIEW (Table Management)
# ============================================================================
# The main dashboard for cashiers - shows all active floors and their tables.
# Each table shows occupancy status (via Table.is_occupied property).
# Clicking a table takes you to the order screen for that table.
# ============================================================================

@login_required
def floor_view(request):
    """Display all floors and tables with their current status."""
    session = _get_or_open_session(request.user)
    # Prefetch tables to avoid N+1 queries when checking occupancy
    floors = Floor.objects.filter(is_active=True).prefetch_related("tables")
    context = {
        "session": session,
        "floors": floors,
    }
    return render(request, "pos/floor.html", context)


# ============================================================================
# SECTION 4: ORDER SCREEN (Order Management - Core POS Functionality)
# ============================================================================
# The heart of the POS system. Cashiers select a table, add items to an order,
# update quantities, and send orders to the kitchen.
#
# Order status flow: OPEN (can edit) → SENT (locked, kitchen working) → PAID
# Once sent, cashiers can't modify the order unless they have manager privileges
# (we should add that check eventually).
# ============================================================================

@login_required
def order_view(request, table_id):
    """
    Main order entry screen for a specific table.
    
    Fetches or creates an open order for this table/session combination.
    Shows categories, products, and current order lines.
    """
    table = get_object_or_404(Table, pk=table_id, is_active=True)
    session = _get_or_open_session(request.user)

    # Get existing open/sent order or create a fresh one
    # We exclude PAID and CANCELLED orders because they're done
    order = Order.objects.filter(
        session=session, table=table, status__in=["open", "sent"]
    ).first()
    if not order:
        order = Order.objects.create(session=session, table=table)

    # Only show categories that have at least one available product
    # Prefetch products to reduce queries when rendering the menu
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
    """
    AJAX endpoint: Add a product to an order or increment quantity if already exists.
    
    Handles variants (e.g., "Large Coffee") by adjusting the unit price.
    Returns JSON with updated cart totals for real-time UI updates.
    """
    order = get_object_or_404(Order, pk=order_id, session__user=request.user, status__in=["open", "sent"])
    product_id = request.POST.get("product_id")
    variant_id = request.POST.get("variant_id") or None
    product = get_object_or_404(Product, pk=product_id, is_available=True)
    
    # Calculate price: base product price + variant upcharge (if any)
    variant = None
    unit_price = product.price
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
        unit_price += variant.extra_price

    # Use get_or_create to handle adding vs incrementing
    # If line exists, we just bump quantity by 1
    line, created = OrderLine.objects.get_or_create(
        order=order, product=product, variant=variant,
        defaults={"unit_price": unit_price, "tax_rate": product.tax_rate},
    )
    if not created:
        line.quantity += 1
        line.save()

    order.recalculate()  # Update all totals
    return JsonResponse({
        "ok": True,
        "line_id": line.pk,
        "qty": line.quantity,
        "line_total": str(line.line_total),
        "subtotal": str(order.subtotal),
        "tax_total": str(order.tax_total),
        "grand_total": str(order.grand_total),
    })


@login_required
@require_POST
def update_item_view(request, line_id):
    """
    AJAX endpoint: Update quantity of an existing order line.
    
    If quantity is 0 or negative, delete the line entirely.
    Returns updated totals for the UI.
    """
    line = get_object_or_404(OrderLine, pk=line_id, order__session__user=request.user)
    qty = int(request.POST.get("qty", 0))
    
    if qty <= 0:
        # Remove item from order
        line.delete()
        line.order.recalculate()
        return JsonResponse({
            "ok": True, 
            "grand_total": str(line.order.grand_total),
            "subtotal": str(line.order.subtotal),
            "tax_total": str(line.order.tax_total),
        })
    else:
        line.quantity = qty
        line.save()
        line.order.recalculate()
        return JsonResponse({
            "ok": True,
            "grand_total": str(line.order.grand_total),
            "subtotal": str(line.order.subtotal),
            "tax_total": str(line.order.tax_total),
            "line_total": str(line.line_total),
            "qty": line.quantity,
        })


@login_required
@require_POST
def send_to_kitchen_view(request, order_id):
    """
    Mark order as "sent" and create a kitchen ticket.
    
    This locks the order from further editing (in the UI at least - we should
    enforce this at the model level with a status check).
    Kitchen staff will see this order on their display.
    """
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    
    # Defensive: Don't allow empty orders to be sent (prevents kitchen confusion)
    if not order.lines.exists():
        messages.error(request, "Cannot send empty order to kitchen.")
        return redirect("pos:order", table_id=order.table_id)

    order.status = Order.SENT
    order.save()

    # Create kitchen ticket if it doesn't exist (shouldn't happen, but being safe)
    KitchenTicket.objects.get_or_create(order=order)
    messages.success(request, f"Order #{order.pk} sent to kitchen.")
    return redirect("pos:order", table_id=order.table_id)


# ============================================================================
# SECTION 5: PAYMENT SCREEN (Checkout & Billing)
# ============================================================================
# Handles the payment flow: display QR for UPI, process cash/card, and confirm.
#
# Important: UPI QR generation uses an external API (qrserver.com). This is a
# free service but has rate limits. In production, consider generating QR codes
# locally or using a paid service with higher limits.
# ============================================================================

@login_required
def payment_view(request, order_id):
    """
    Payment screen: shows order summary and available payment methods.
    
    For UPI payments, generates a QR code with the amount pre-filled.
    The QR code uses the UPI URI scheme so customers can scan and pay directly.
    """
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    payment_methods = PaymentMethod.objects.filter(is_enabled=True)
    upi_method = payment_methods.filter(type="upi").first()

    # Generate UPI QR code if UPI is enabled and has an ID configured
    qr_url = None
    if upi_method and upi_method.upi_id:
        upi_string = (
            f"upi://pay"
            f"?pa={upi_method.upi_id}"           # Payee VPA (Virtual Payment Address)
            f"&pn=CafePOS"                        # Payee name
            f"&am={order.grand_total:.2f}"        # Amount (pre-filled)
            f"&tn=Table{order.table.number}"      # Transaction note for reference
            f"&cu=INR"                            # Currency
        )
        # Using free QR API - replace with local generation for production
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={quote(upi_string)}"

    context = {
        "order": order,
        "payment_methods": payment_methods,
        "upi_method": upi_method,
        "qr_url": qr_url,
        "lines": order.lines.select_related("product").all(),
    }
    return render(request, "pos/payment.html", context)


@login_required
@require_POST
def process_payment_view(request, order_id):
    """
    Process payment and mark order as paid.
    
    Validates that the payment method is enabled (in case someone tampers with the form).
    Once paid, the order is considered complete and can't be modified.
    """
    order = get_object_or_404(Order, pk=order_id, session__user=request.user)
    method = request.POST.get("method")

    # Security: Only allow payment methods that are currently enabled
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
    """Receipt/confirmation screen after successful payment."""
    order = get_object_or_404(Order, pk=order_id, session__user=request.user, status="paid")
    return render(request, "pos/payment_confirm.html", {"order": order})


# ============================================================================
# SECTION 6: KITCHEN DISPLAY (Kitchen Monitor)
# ============================================================================
# This view is intentionally NOT login-protected because it runs on a dedicated
# tablet in the kitchen. Kitchen staff don't need user accounts.
#
# Workflow: Orders appear in "To Cook" → Kitchen marks as "Preparing" → "Completed"
# Completed orders are automatically hidden from the main list but kept for history.
# ============================================================================

def kitchen_view(request):
    """
    Kitchen display screen - no authentication required (kiosk-style).
    
    Shows all non-completed tickets plus the 10 most recently completed ones
    for context. Uses select_related/prefetch_related to optimize query performance
    since this page refreshes frequently.
    """
    # Active tickets (everything except completed)
    tickets = KitchenTicket.objects.exclude(stage="completed").select_related(
        "order", "order__table"
    ).prefetch_related("order__lines__product")
    
    # Last 10 completed tickets for reference (ordered by most recent)
    completed = KitchenTicket.objects.filter(stage="completed").select_related(
        "order", "order__table"
    ).order_by("-updated_at")[:10]
    
    return render(request, "pos/kitchen.html", {"tickets": tickets, "completed": completed})


@require_POST
def advance_ticket_view(request, ticket_id):
    """
    AJAX endpoint: Move kitchen ticket to next stage.
    
    Stages: TO_COOK → PREPARING → COMPLETED
    Called when kitchen staff taps "Mark as Preparing" or "Mark as Complete".
    """
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    ticket.advance()  # State machine logic is in the model
    return JsonResponse({"ok": True, "stage": ticket.stage})


@require_POST
def mark_line_prepared_view(request, line_id):
    """
    AJAX endpoint: Toggle prepared status for individual order lines.
    
    Kitchen staff can mark specific items as done (e.g., "Burger done, fries still cooking").
    This shows as a strikethrough in the kitchen UI.
    """
    line = get_object_or_404(OrderLine, pk=line_id)
    line.is_prepared = not line.is_prepared
    line.save()
    return JsonResponse({"ok": True, "prepared": line.is_prepared})


# ============================================================================
# SECTION 7: CUSTOMER DISPLAY (Guest-facing Screen)
# ============================================================================
# Shows the current order to customers so they can see what they've ordered
# and track preparation status. Runs on a separate screen/monitor.
# ============================================================================

def customer_display_view(request, order_id):
    """
    Customer-facing display - no authentication required.
    
    Shows a clean, read-only view of the order. Useful for large TVs mounted
    in the dining area so customers can verify their order.
    """
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "pos/customer_display.html", {
        "order": order,
        "lines": order.lines.select_related("product").all(),
    })


# ============================================================================
# SECTION 8: SELF-ORDERING (QR Code-based Ordering)
# ============================================================================
# Optional feature: Customers scan a QR code on their table, which takes them
# to this view. They can add items to their order from their phone.
#
# Security: Orders are identified by a UUID token embedded in the QR code.
# This prevents customers from accessing other tables' orders.
# ============================================================================

def self_order_view(request, token):
    """
    Mobile/self-ordering interface - customers order from their phones.
    
    The token is a UUID that's unique to each order. When customers add items,
    the order is automatically sent to the kitchen without cashier intervention.
    
    TODO: Add order limits (prevent adding items after kitchen starts cooking)
    """
    order = get_object_or_404(Order, self_order_token=token)
    categories = Category.objects.prefetch_related("products").filter(
        products__is_available=True
    ).distinct()

    if request.method == "POST":
        # Add item to order (similar to add_item_view but without AJAX)
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
        
        # Auto-send to kitchen so staff can start preparing immediately
        if order.status == Order.OPEN:
            order.status = Order.SENT
            order.save()
            KitchenTicket.objects.get_or_create(order=order)

    return render(request, "pos/self_order.html", {
        "order": order,
        "categories": categories,
        "lines": order.lines.select_related("product").all(),
    })


# ============================================================================
# SECTION 9: POS BACKEND CONFIGURATION (Admin Dashboard)
# ============================================================================
# Manager-level views for configuring the POS system:
# - Toggle payment methods on/off
# - View product and category counts
# - Manage floors and tables
# ============================================================================

@login_required
def backend_view(request):
    """
    Backend configuration dashboard - managers only (should add permission check).
    
    Displays system status, current session, and links to configuration sections.
    Also shows summary statistics at a glance.
    """
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
    """
    AJAX endpoint: Enable/disable a payment method.
    
    Used by managers to temporarily disable a payment type if the gateway is down
    or if there's an issue with the card machine.
    """
    pm = get_object_or_404(PaymentMethod, pk=pm_id)
    pm.is_enabled = not pm.is_enabled
    pm.save()
    return JsonResponse({"ok": True, "enabled": pm.is_enabled})


# ============================================================================
# SECTION 10: REPORTS & ANALYTICS (Sales Reporting)
# ============================================================================
# Comprehensive reporting view with filters for date range, session, cashier, and product.
# Shows total revenue, order count, and detailed order list.
#
# Performance note: This query can get slow with large datasets. Consider adding
# pagination and database indexes on updated_at, session_id, and user_id.
# ============================================================================

@login_required
def reports_view(request):
    """
    Sales reports dashboard with filtering and aggregation.
    
    Filters:
    - Period: Today, This Week, Custom Range
    - Session ID: Filter by specific POS session
    - Cashier: Filter by responsible staff member
    - Product: Show orders containing a specific product
    
    Returns aggregated totals and a list of matching orders.
    """
    from django.db.models import Sum, Count, Q
    from datetime import date, timedelta

    # --- Parse filters from request ---
    period = request.GET.get("period", "today")
    session_id = request.GET.get("session_id", "")
    responsible_id = request.GET.get("responsible_id", "")
    product_id = request.GET.get("product_id", "")

    # Base queryset: only paid orders (cancelled/open orders shouldn't count)
    orders = Order.objects.filter(status="paid")

    today = date.today()
    
    # Apply date range filters
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

    # Apply other filters
    if session_id:
        orders = orders.filter(session_id=session_id)
    if responsible_id:
        orders = orders.filter(session__user_id=responsible_id)
    if product_id:
        orders = orders.filter(lines__product_id=product_id)

    # Aggregate totals for the filtered dataset
    agg = orders.aggregate(
        total_revenue=Sum("grand_total"),
        total_orders=Count("id", distinct=True),
    )

    # Prepare context with filter options for the UI
    context = {
        "orders": orders.select_related("table", "session__user").order_by("-updated_at")[:50],  # Limit to 50 for performance
        "total_revenue": agg["total_revenue"] or 0,
        "total_orders": agg["total_orders"] or 0,
        "period": period,
        "sessions": POSSession.objects.order_by("-opened_at")[:20],
        "users": user.objects.filter(pos_sessions__isnull=False).distinct(),  # Only users who have POS sessions
        "products": Product.objects.all(),
        "selected_session": session_id,
        "selected_responsible": responsible_id,
        "selected_product": product_id,
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }
    return render(request, "pos/reports.html", context)
