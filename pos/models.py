from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

# ============================================================================
# SECTION 1: Floor & Table Management
# ============================================================================
# Physical layout of the restaurant - floors contain tables, tables hold orders
# This hierarchy allows us to support multi-floor restaurants (ground, first, rooftop, etc.)
# ============================================================================

class Floor(models.Model):
    """Represents a physical floor/level in the restaurant"""
    name = models.CharField(max_length=100)  # e.g. "Ground Floor", "Mezzanine", "Rooftop Garden"
    is_active = models.BooleanField(default=True)  # Soft delete - we keep data but hide from UI
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]  # Alphabetical order makes dropdowns predictable


class Table(models.Model):
    """Physical table on a specific floor where customers sit and order"""
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()        # Table 3, Table 6 - human readable identifier
    seats = models.PositiveIntegerField(default=4)  # Capacity, useful for reservation logic later
    is_active = models.BooleanField(default=True)
    
    # Legacy field from previous system - maps to external booking/reservation API
    # Kept for compatibility but can be ignored for new features
    appointment_resource = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Table {self.number} ({self.floor.name})"

    class Meta:
        ordering = ["floor", "number"]  # Natural grouping: all floor 1 tables first
        unique_together = [("floor", "number")]  # No duplicate table numbers on same floor

    @property
    def is_occupied(self):
        """Quick check if table currently has an active order (open or sent to kitchen)"""
        # Returns True if any order exists that's not yet paid or cancelled
        return self.orders.filter(status__in=["open", "sent"]).exists()


# ============================================================================
# SECTION 2: Menu Structure (Categories, Products, Variants)
# ============================================================================
# Classic e-commerce style hierarchy: Category -> Product -> Variant
# Examples: "Beverages" -> "Coffee" -> "Size: Large"
# The send_to_kitchen flag lets us separate bar items from kitchen items
# ============================================================================

class Category(models.Model):
    """Menu category - groups related products (Appetizers, Main Course, Desserts, etc.)"""
    name = models.CharField(max_length=100)
    send_to_kitchen = models.BooleanField(default=True)  # False = bar/beverage items (no kitchen ticket)
    display_order = models.PositiveIntegerField(default=0)  # Custom sort order in UI

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]  # Respect custom order, fallback to alphabet


class Product(models.Model):
    """Individual menu item that can be ordered"""
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)  # Photo for menu display
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
        # SET_NULL preserves products even if category gets deleted (good for historical orders)
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Base price before tax
    unit = models.CharField(max_length=50, default="piece")  # piece, plate, bottle, kg, etc.
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # GST/VAT as percentage
    description = models.TextField(blank=True)  # Long description for menu displays
    is_available = models.BooleanField(default=True)  # Out of stock? Temporarily unavailable?
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["category", "name"]

    @property
    def price_with_tax(self):
        """Helper for displaying final price to customer"""
        return self.price * (1 + self.tax_rate / 100)


class ProductVariant(models.Model):
    """Modifiers/options for a product (e.g., "Size: Small/Medium/Large", "Spice Level: Mild/Spicy")"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=100)  # e.g., "Size", "Temperature", "Spice Level"
    value = models.CharField(max_length=100)      # e.g., "Large", "Iced", "Extra Spicy"
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Additional charge

    def __str__(self):
        return f"{self.product.name} — {self.attribute}: {self.value}"


# ============================================================================
# SECTION 3: Payments
# ============================================================================
# Simple payment method catalog - which payment types are enabled for this location
# Unique constraint on 'type' ensures we don't have duplicate payment methods
# ============================================================================

class PaymentMethod(models.Model):
    """Available payment types (configurable per restaurant location)"""
    CASH = "cash"
    DIGITAL = "digital"
    UPI = "upi"
    TYPE_CHOICES = [
        (CASH, "Cash"),
        (DIGITAL, "Digital / Card"),
        (UPI, "UPI QR"),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, unique=True)
    is_enabled = models.BooleanField(default=True)  # Can toggle off temporarily if payment gateway is down
    upi_id = models.CharField(max_length=100, blank=True)  # Only used when type = UPI

    def __str__(self):
        return self.get_type_display()


# ============================================================================
# SECTION 4: POS Sessions (Cash Drawer Management)
# ============================================================================
# Critical for accountability - tracks when a cashier starts/ends their shift
# A session can have multiple orders, and closing calculates total sales for handover
# Each user can only have one OPEN session at a time (enforced in views)
# ============================================================================

class POSSession(models.Model):
    """Represents a cashier's work shift - opening and closing balances"""
    OPEN = "open"
    CLOSED = "closed"
    STATUS_CHOICES = [(OPEN, "Open"), (CLOSED, "Closed")]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="pos_sessions")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_sale_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # Auto-calculated on close
    notes = models.TextField(blank=True)  # Manager notes, cash discrepancies, etc.

    def __str__(self):
        return f"Session #{self.pk} — {self.user} ({self.status})"

    def close(self):
        """Close the session: calculate total sales from paid orders and mark closed"""
        from django.db.models import Sum
        total = self.orders.filter(status="paid").aggregate(s=Sum("grand_total"))["s"] or 0
        self.closing_sale_amount = total
        self.closed_at = timezone.now()
        self.status = self.CLOSED
        self.save()

    class Meta:
        ordering = ["-opened_at"]  # Newest sessions first


# ============================================================================
# SECTION 5: Orders & Order Lines (The Core Transaction Logic)
# ============================================================================
# Heart of the POS system - an Order belongs to a Session and optionally a Table
# Status flow: OPEN (editing) -> SENT (to kitchen) -> PAID (completed) -> CANCELLED (voided)
# self_order_token allows QR code based self-ordering (customer scans, orders from their phone)
# ============================================================================

class Order(models.Model):
    """Customer order - can be dine-in (with table) or takeaway (table = null)"""
    OPEN = "open"
    SENT = "sent"      # Sent to kitchen, can't edit unless manager overrides
    PAID = "paid"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (OPEN, "Open"),
        (SENT, "Sent to Kitchen"),
        (PAID, "Paid"),
        (CANCELLED, "Cancelled"),
    ]

    PAYMENT_CASH = "cash"
    PAYMENT_DIGITAL = "digital"
    PAYMENT_UPI = "upi"
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, "Cash"),
        (PAYMENT_DIGITAL, "Digital / Card"),
        (PAYMENT_UPI, "UPI QR"),
    ]

    session = models.ForeignKey(POSSession, on_delete=models.CASCADE, related_name="orders")
    table = models.ForeignKey(
        Table, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
        # SET_NULL preserves orders even if table is deleted (for reporting)
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, blank=True, null=True
        # Null until payment is completed
    )
    
    # Financial fields - denormalized for performance (avoid recalculating from lines every time)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)  # Special instructions for kitchen
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Unique token for customer self-ordering via QR code
    # UUID ensures it's globally unique and not guessable
    self_order_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"Order #{self.pk} — {self.table} ({self.status})"

    def recalculate(self):
        """Recompute all financial totals from order lines.
        Called after adding/removing/updating items in the order."""
        subtotal = sum(line.line_total for line in self.lines.all())
        tax_total = sum(line.tax_amount for line in self.lines.all())
        self.subtotal = subtotal
        self.tax_total = tax_total
        self.grand_total = subtotal + tax_total
        self.save(update_fields=["subtotal", "tax_total", "grand_total"])

    class Meta:
        ordering = ["-created_at"]  # Most recent orders first


class OrderLine(models.Model):
    """Individual line item within an order (e.g., "3x Burger, Large size")"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
        # SET_NULL preserves order line even if variant is deleted from menu
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order (snapshot)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Snapshot of tax rate
    is_prepared = models.BooleanField(default=False)  # Kitchen staff marks as done (visual strikethrough)

    def __str__(self):
        return f"{self.quantity}× {self.product.name}"

    @property
    def line_total(self):
        """Total price for this line (unit_price × quantity)"""
        return self.unit_price * self.quantity

    @property
    def tax_amount(self):
        """Tax amount for this line based on snapshot tax_rate"""
        return self.line_total * self.tax_rate / 100


# ============================================================================
# SECTION 6: Kitchen Tickets (Kitchen Display System Integration)
# ============================================================================
# One-to-one with Order - tracks the progress of food preparation
# Workflow: TO_COOK → PREPARING → COMPLETED
# Kitchen staff updates this via their tablet/large display
# ============================================================================

class KitchenTicket(models.Model):
    """Kitchen-facing view of an order - tracks cooking progress independently of payment"""
    TO_COOK = "to_cook"
    PREPARING = "preparing"
    COMPLETED = "completed"
    STAGE_CHOICES = [
        (TO_COOK, "To Cook"),
        (PREPARING, "Preparing"),
        (COMPLETED, "Completed"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="kitchen_ticket")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=TO_COOK)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def advance(self):
        """Move to next stage: TO_COOK → PREPARING → COMPLETED"""
        # Simple state machine - could be extended to skip steps if needed
        transitions = {self.TO_COOK: self.PREPARING, self.PREPARING: self.COMPLETED}
        self.stage = transitions.get(self.stage, self.stage)
        self.save()

    def __str__(self):
        return f"Ticket #{self.order_id} — {self.stage}"

    class Meta:
        ordering = ["created_at"]  # Oldest tickets first (FIFO for kitchen)
