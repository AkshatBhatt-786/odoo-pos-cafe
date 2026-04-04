from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def dashboard(request):
    context = {
        'user': request.user,
        'active_session': None,
        'today_orders': 0,
        'today_revenue': 0,
    }
    return render(request, 'pos/dashboard.html', context)

@login_required
def floor_view(request):
    """Floor/Table management view"""
    return render(request, 'pos/floor.html', {'user': request.user})

@login_required
def kitchen_view(request):
    """Kitchen display view"""
    return render(request, 'pos/kitchen.html', {'user': request.user})

@login_required
def reports_view(request):
    """Reports dashboard view"""
    return render(request, 'pos/reports.html', {'user': request.user})