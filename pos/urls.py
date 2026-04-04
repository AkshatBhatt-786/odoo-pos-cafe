from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('floor/', views.floor_view, name='floor'),
    path('kitchen/', views.kitchen_view, name='kitchen'),
    path('reports/', views.reports_view, name='reports'),
]