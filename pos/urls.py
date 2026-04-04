from django.urls import path
from . import views

app_name = "pos"

urlpatterns = [
    # Session
    path("open-session/",  views.open_session_view,  name="open_session"),
    path("close-session/", views.close_session_view, name="close_session"),

    # Frontend
    path("floor/",                          views.floor_view,           name="floor"),
    path("order/<int:table_id>/",           views.order_view,           name="order"),
    path("order/<int:order_id>/add/",       views.add_item_view,        name="add_item"),
    path("order/<int:order_id>/send/",      views.send_to_kitchen_view, name="send_to_kitchen"),
    path("line/<int:line_id>/update/",      views.update_item_view,     name="update_item"),
    path("payment/<int:order_id>/",         views.payment_view,         name="payment"),
    path("payment/<int:order_id>/process/", views.process_payment_view, name="process_payment"),
    path("payment/<int:order_id>/confirm/", views.payment_confirm_view, name="payment_confirm"),

    # Kitchen & Customer
    path("kitchen/",                          views.kitchen_view,           name="kitchen"),
    path("kitchen/ticket/<int:ticket_id>/advance/", views.advance_ticket_view, name="advance_ticket"),
    path("kitchen/line/<int:line_id>/prepared/",    views.mark_line_prepared_view, name="mark_line_prepared"),
    path("customer/<int:order_id>/",          views.customer_display_view,  name="customer_display"),

    # Self ordering
    path("self-order/<uuid:token>/",          views.self_order_view,        name="self_order"),

    # Backend & Reports
    path("backend/",                          views.backend_view,           name="backend"),
    path("backend/payment/<int:pm_id>/toggle/", views.toggle_payment_method_view, name="toggle_payment"),
    path("reports/",                          views.reports_view,           name="reports"),
]