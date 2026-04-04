from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

# ─────────────────────────────────────────────
#  FLOOR & TABLE
# ─────────────────────────────────────────────

class Floor(models.Model):
    name = models.CharField(max_length=100)  # e.g. "Ground Floor"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Table(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()        # Table 3, Table 6 …
    seats = models.PositiveIntegerField(default=4)
    is_active = models.BooleanField(default=True)
    appointment_resource = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Table {self.number} ({self.floor.name})"

    class Meta:
        ordering = ["floor", "number"]
        unique_together = [("floor", "number")]

    @property
    def is_occupied(self):
        return self.orders.filter(status__in=["open", "sent"]).exists()


# ─────────────────────────────────────────────
#  PRODUCT
# ─────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=100)
    send_to_kitchen = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default="piece")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percent
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["category", "name"]

    @property
    def price_with_tax(self):
        return self.price * (1 + self.tax_rate / 100)


class ProductVariant(models.Model):
    """Optional variants e.g. Pack → 6 items / 12 items with extra price."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=100)   # e.g. "Pack"
    value = models.CharField(max_length=100)        # e.g. "6 items"
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product.name} — {self.attribute}: {self.value}"


# ─────────────────────────────────────────────
#  PAYMENT METHOD
# ─────────────────────────────────────────────

class PaymentMethod(models.Model):
    CASH = "cash"
    DIGITAL = "digital"
    UPI = "upi"
    TYPE_CHOICES = [
        (CASH, "Cash"),
        (DIGITAL, "Digital / Card"),
        (UPI, "UPI QR"),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, unique=True)
    is_enabled = models.BooleanField(default=True)
    upi_id = models.CharField(max_length=100, blank=True)  # only for UPI

    def __str__(self):
        return self.get_type_display()


# ─────────────────────────────────────────────
#  POS SESSION
# ─────────────────────────────────────────────

class POSSession(models.Model):
    OPEN = "open"
    CLOSED = "closed"
    STATUS_CHOICES = [(OPEN, "Open"), (CLOSED, "Closed")]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="pos_sessions")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_sale_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Session #{self.pk} — {self.user} ({self.status})"

    def close(self):
        from django.db.models import Sum
        total = self.orders.filter(status="paid").aggregate(s=Sum("grand_total"))["s"] or 0
        self.closing_sale_amount = total
        self.closed_at = timezone.now()
        self.status = self.CLOSED
        self.save()

    class Meta:
        ordering = ["-opened_at"]


# ─────────────────────────────────────────────
#  ORDER
# ─────────────────────────────────────────────

class Order(models.Model):
    OPEN = "open"
    SENT = "sent"        # sent to kitchen
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
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, blank=True, null=True
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Self-ordering token
    self_order_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"Order #{self.pk} — {self.table} ({self.status})"

    def recalculate(self):
        """Recompute subtotal, tax, grand_total from order lines."""
        subtotal = sum(line.line_total for line in self.lines.all())
        tax_total = sum(line.tax_amount for line in self.lines.all())
        self.subtotal = subtotal
        self.tax_total = tax_total
        self.grand_total = subtotal + tax_total
        self.save(update_fields=["subtotal", "tax_total", "grand_total"])

    class Meta:
        ordering = ["-created_at"]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_prepared = models.BooleanField(default=False)  # kitchen struck-through

    def __str__(self):
        return f"{self.quantity}× {self.product.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def tax_amount(self):
        return self.line_total * self.tax_rate / 100


# ─────────────────────────────────────────────
#  KITCHEN TICKET  (mirrors Order for kitchen)
# ─────────────────────────────────────────────

class KitchenTicket(models.Model):
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
        transitions = {self.TO_COOK: self.PREPARING, self.PREPARING: self.COMPLETED}
        self.stage = transitions.get(self.stage, self.stage)
        self.save()

    def __str__(self):
        return f"Ticket #{self.order_id} — {self.stage}"

    class Meta:
        ordering = ["created_at"]