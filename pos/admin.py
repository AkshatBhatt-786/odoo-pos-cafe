from django.contrib import admin
from .models import (
    Floor, Table, Category, Product, ProductVariant,
    PaymentMethod, POSSession, Order, OrderLine, KitchenTicket
)


class TableInline(admin.TabularInline):
    model = Table
    extra = 1


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    inlines = [TableInline]


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ["number", "floor", "seats", "is_active"]
    list_filter = ["floor", "is_active"]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "send_to_kitchen", "display_order"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "tax_rate", "is_available"]
    list_filter = ["category", "is_available"]
    inlines = [ProductVariantInline]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["type", "is_enabled", "upi_id"]


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(POSSession)
class POSSessionAdmin(admin.ModelAdmin):
    list_display = ["pk", "user", "status", "opened_at", "closing_sale_amount"]
    list_filter = ["status"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["pk", "table", "status", "payment_method", "grand_total", "created_at"]
    list_filter = ["status", "payment_method"]
    inlines = [OrderLineInline]


@admin.register(KitchenTicket)
class KitchenTicketAdmin(admin.ModelAdmin):
    list_display = ["order", "stage", "created_at"]
    list_filter = ["stage"]