from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import SignupForm
from .models import User

def login_view(request):
    """User login view with custom template"""
    if request.user.is_authenticated:
        return redirect('pos:dashboard')
    
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Handle remember me
            if not remember_me:
                request.session.set_expiry(0)  # Session expires on browser close
            
            messages.success(request, f'Welcome back, {username}!')
            
            # Redirect to next parameter or dashboard
            next_url = request.GET.get('next', 'pos:dashboard')
            return redirect(next_url)
        else:
            error = 'Invalid username or password. Please try again.'
    
    return render(request, 'accounts/login.html', {'error': error})

def signup_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('pos:dashboard')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.username}! Your account has been created.')
            return redirect('pos:dashboard')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = SignupForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def logout_view(request):
    """User logout view"""
    # Clear session data if needed
    if hasattr(request.user, 'is_active_session') and request.user.is_active_session:
        request.user.is_active_session = False
        request.user.current_session_id = None
        request.user.save()
    
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')

@login_required
def profile_view(request):
    """User profile view"""
    if request.method == 'POST':
        # Update profile logic
        user = request.user
        user.phone = request.POST.get('phone', user.phone)
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile.html', {'user': request.user})