from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import SignupForm
from .models import User

# ----------------------------------------------------------------------
# Login View - handles user authentication and session management
# ----------------------------------------------------------------------
# Pretty standard login flow, but with a few custom touches:
# 1. "Remember me" functionality (session expiry control)
# 2. Redirects already-logged-in users to the POS floor
# 3. Supports next parameter for deep linking
# ----------------------------------------------------------------------
def login_view(request):
    """User login view with custom template"""
    
    # If user is somehow already logged in, send them straight to work
    # Prevents weird edge cases where someone bookmarks the login page
    if request.user.is_authenticated:
        return redirect('pos:floor')
    
    error = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')  # This comes from a checkbox
        
        # Let Django handle the heavy lifting of password verification
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Credentials are good - log them in
            login(request, user)
            
            # Handle remember me: if unchecked, session dies when browser closes
            # Checked = default Django behavior (session lasts SESSION_COOKIE_AGE)
            if not remember_me:
                request.session.set_expiry(0)  # 0 = expires on browser close
            
            messages.success(request, f'Welcome back, {username}!')
            
            # Redirect priority: next parameter > default POS floor
            # This is useful for protected pages that redirect to login
            next_url = request.GET.get('next', 'pos:floor')
            return redirect(next_url)
        else:
            # Failed login - show generic error (don't reveal if user exists or not)
            error = 'Invalid username or password. Please try again.'
    
    return render(request, 'accounts/login.html', {'error': error})


# ----------------------------------------------------------------------
# Signup View - new user registration
# ----------------------------------------------------------------------
# Using our custom SignupForm which adds email, phone, and role fields.
# After successful signup, we automatically log the user in to reduce friction.
# No email verification yet, but that's coming in v2.
# ----------------------------------------------------------------------
def signup_view(request):
    """User registration view"""
    
    # Already signed up? No need to see the registration form again
    if request.user.is_authenticated:
        return redirect('pos:floor')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()  # This creates and saves the user
            login(request, user)  # Auto-login after registration (user-friendly)
            messages.success(request, f'Welcome {user.username}! Your account has been created.')
            return redirect('pos:floor')
        else:
            # Form has errors - loop through and show each one
            # Slightly crude but gets the job done until we build better error UI
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = SignupForm()
    
    return render(request, 'accounts/signup.html', {'form': form})


# ----------------------------------------------------------------------
# Logout View - session cleanup and user sign-out
# ----------------------------------------------------------------------
# Important: We need to clean up the user's active POS session before logging out.
# If we don't, the user would still appear "active" in the system and couldn't
# log back in on another terminal. This prevents session ghosting.
# ----------------------------------------------------------------------
@login_required
def logout_view(request):
    """User logout view"""
    
    # Check if user has an active POS session and clean it up
    # Using hasattr as a safety check in case this view gets called on a non-custom User
    if hasattr(request.user, 'is_active_session') and request.user.is_active_session:
        request.user.is_active_session = False
        request.user.current_session_id = None
        request.user.save()  # Persist the session cleanup
    
    # Now we can safely log them out of Django auth
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')  # Send them to the marketing/landing page


# ----------------------------------------------------------------------
# Profile View - user settings and preferences
# ----------------------------------------------------------------------
# Simple CRUD for user profile data. Currently only handles phone number updates,
# but we'll likely add more fields here (notification preferences, theme, etc.)
# 
# TODO: Add password change functionality and email verification
# ----------------------------------------------------------------------
@login_required
def profile_view(request):
    """User profile view"""
    
    if request.method == 'POST':
        # For now, just updating phone number. Keep it simple.
        # Later we can add a proper form with validation
        user = request.user
        user.phone = request.POST.get('phone', user.phone)  # If no phone provided, keep existing
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')  # Redirect to avoid form resubmission on refresh
    
    # GET request - just show the profile page with current user data
    return render(request, 'accounts/profile.html', {'user': request.user})